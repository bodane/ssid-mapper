import os
import csv
import json
import time
import argparse
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from folium.plugins import MarkerCluster
import folium

# === Settings ===
csv.field_size_limit(1073741824)
load_dotenv()
WIGLE_API_KEY = os.getenv("WIGLE_API_KEY")
CACHE_FILE = os.getenv("CACHE_FILE", "wigle_cache.json")
USE_CLUSTERING = os.getenv("USE_CLUSTERING", "true").lower() == "true"
geolocator = Nominatim(user_agent="wigle_tool")

class Colors:
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"

def color(text, code, use_color=True):
    return f"{code}{text}{Colors.ENDC}" if use_color else text

def parse_datetime(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid datetime format: '{text}', expected 'YYYY-MM-DD HH:MM'.")

class StationProbe:
    def __init__(self, ssid):
        self.ssid = ssid

class AirodumpParser:
    def __init__(self, netxml_path, first_time_range=None, last_time_range=None, verbose=False):
        self.path = netxml_path
        self.first_range = first_time_range
        self.last_range = last_time_range
        self.verbose = verbose

    def parse(self):
        probes = []
        try:
            tree = ET.parse(self.path)
            root = tree.getroot()

            for client in root.findall(".//wireless-client"):
                ssid_elements = client.findall("SSID")
                for ssid_block in ssid_elements:
                    ssid_type = ssid_block.findtext("type")
                    ssid_name = ssid_block.findtext("ssid")
                    if ssid_type != "Probe Request" or not ssid_name:
                        continue

                    # Parse times
                    first_time_str = ssid_block.attrib.get("first-time")
                    last_time_str = ssid_block.attrib.get("last-time")

                    if not first_time_str or not last_time_str:
                        continue

                    first_time = datetime.strptime(first_time_str, "%a %b %d %H:%M:%S %Y")
                    last_time = datetime.strptime(last_time_str, "%a %b %d %H:%M:%S %Y")

                    # Apply filters
                    if self.first_range:
                        if len(self.first_range) == 1:
                            if first_time < self.first_range[0]:
                                continue
                        elif not (self.first_range[0] <= first_time <= self.first_range[1]):
                            continue

                    if self.last_range:
                        if len(self.last_range) == 1:
                            if last_time < self.last_range[0]:
                                continue
                        elif not (self.last_range[0] <= last_time <= self.last_range[1]):
                            continue

                    ssid_name = ssid_name.strip()
                    if not ssid_name:
                        continue

                    if self.verbose:
                        print(f"[DEBUG] Matched SSID '{ssid_name}' with first-time {first_time} and last-time {last_time}")

                    probes.append(StationProbe(ssid_name))

        except ET.ParseError as e:
            print(f"[✗] Failed to parse netxml file: {e}")
        return probes

class WigleClient:
    def __init__(self, api_key, cache_path="wigle_cache.json", use_color=True):
        self.api_key = api_key
        self.cache_path = cache_path
        self.cache = self.load_cache()
        self.use_color = use_color

    def load_cache(self):
        if os.path.exists(self.cache_path):
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_cache(self):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2)

    def search(self, ssid, country_code=None):
        if ssid in self.cache:
            print(color(f"[!] Using cached results for {ssid}", Colors.WARNING, self.use_color))
            return self.cache[ssid]

        url = "https://api.wigle.net/api/v2/network/search"
        headers = {
            "Authorization": f"Basic {self.api_key}",
            "Accept": "application/json"
        }

        params = {
            "ssid": ssid,
            "resultsPerPage": 100,
            "first": 0
        }
        if country_code:
            params["countrycode"] = country_code.upper()

        results = []
        page = 1
        while True:
            print(color(f"[*] Querying WiGLE for '{ssid}' - Page {page}", Colors.OKCYAN, self.use_color))
            resp = requests.get(url, headers=headers, params=params)

            if resp.status_code == 429:
                print(color("[!] Rate limited. Waiting 30s...", Colors.WARNING, self.use_color))
                time.sleep(30)
                continue
            elif resp.status_code != 200:
                print(color(f"[✗] HTTP {resp.status_code} error", Colors.FAIL, self.use_color))
                break

            data = resp.json()
            if not data.get("success"):
                print(color(f"[✗] Failed: {data.get('message')}", Colors.FAIL, self.use_color))
                break

            for r in data.get("results", []):
                lat, lon = r.get("trilat"), r.get("trilong")
                if lat and lon:
                    results.append({
                        "ssid": ssid,
                        "bssid": r.get("netid"),
                        "lat": lat,
                        "lon": lon
                    })

            if data.get("totalResults", 0) > params["first"] + params["resultsPerPage"]:
                params["first"] += params["resultsPerPage"]
                page += 1
                time.sleep(1)
            else:
                break

        self.cache[ssid] = results
        self.save_cache()
        print(color(f"[✓] Retrieved {len(results)} result(s) for {ssid}", Colors.OKGREEN, self.use_color))
        return results

def reverse_geocode(lat, lon, max_retries=3):
    for _ in range(max_retries):
        try:
            loc = geolocator.reverse((lat, lon), timeout=10)
            return loc.address if loc else "Unknown"
        except Exception:
            time.sleep(2)
    return "Geocode Failed"

def export_to_csv(results, filename):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ssid", "bssid", "lat", "lon", "address"])
        writer.writeheader()
        for row in results:
            row["address"] = reverse_geocode(row["lat"], row["lon"])
            writer.writerow(row)
            time.sleep(1)

def generate_map(results, filename="wigle_map.html", use_cluster=True):
    if not results:
        return
    map_obj = folium.Map(location=[results[0]["lat"], results[0]["lon"]], zoom_start=12)
    cluster = MarkerCluster().add_to(map_obj) if use_cluster else None

    for r in results:
        marker = folium.Marker([r["lat"], r["lon"]], popup=f"{r['ssid']} ({r['bssid']})")
        if cluster:
            marker.add_to(cluster)
        else:
            marker.add_to(map_obj)

    map_obj.save(filename)

def main():
    parser = argparse.ArgumentParser(description="WiGLE SSID lookup tool (OOP version)")
    parser.add_argument("--netxml", help="Airodump-ng netxml file")
    parser.add_argument("--ssid", help="Direct SSID to search")
    parser.add_argument("--country-code")
    parser.add_argument("--output-prefix", default="wigle_results")
    parser.add_argument("--first-time", nargs='+', type=parse_datetime, help="1 or 2 'first-time' values")
    parser.add_argument("--last-time", nargs='+', type=parse_datetime, help="1 or 2 'last-time' values")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    use_color = not args.no_color
    wigle = WigleClient(WIGLE_API_KEY, use_color=use_color)
    probes = []

    if args.netxml:
        if args.first_time and len(args.first_time) > 2:
            parser.error("--first-time accepts max 2 values")
        if args.last_time and len(args.last_time) > 2:
            parser.error("--last-time accepts max 2 values")

        print(color("[*] Parsing netxml...", Colors.OKCYAN, use_color))
        netxml_parser = AirodumpParser(
            args.netxml,
            first_time_range=args.first_time,
            last_time_range=args.last_time,
            verbose=args.debug
        )
        probes = netxml_parser.parse()
    elif args.ssid:
        probes = [StationProbe(args.ssid)]
    else:
        print(color("[✗] Provide either --netxml or --ssid", Colors.FAIL, use_color))
        return

    seen = set()
    final_results = []

    for probe in probes:
        if probe.ssid in seen:
            continue
        seen.add(probe.ssid)
        results = wigle.search(probe.ssid, country_code=args.country_code)
        final_results.extend(results)
        time.sleep(1)

    if final_results:
        csv_file = f"{args.output_prefix}.csv"
        html_file = f"{args.output_prefix}.html"
        export_to_csv(final_results, csv_file)
        generate_map(final_results, filename=html_file, use_cluster=USE_CLUSTERING)
        print(color(f"[✓] Export complete.\n - {csv_file}\n - {html_file}", Colors.OKGREEN, use_color))
    else:
        print(color("[!] No WiGLE results found.", Colors.WARNING, use_color))

if __name__ == "__main__":
    main()
