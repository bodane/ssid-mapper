import csv
import os
import requests
import folium
import json
import time
import argparse
from folium.plugins import MarkerCluster
from dotenv import load_dotenv
from datetime import datetime
from geopy.geocoders import Nominatim
from time import sleep

# === Colors ===
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

USE_COLORS = True

def color(text, color_code):
    if USE_COLORS:
        return f"{color_code}{text}{Colors.ENDC}"
    return text

# === Load .env Configuration ===
load_dotenv()

WIGLE_API_KEY = os.getenv("WIGLE_API_KEY")
USE_CLUSTERING = os.getenv("USE_CLUSTERING", "true").lower() == "true"
CACHE_FILE = os.getenv("CACHE_FILE", "wigle_cache.json")

# === Geocoding Function with Retry and Delay ===
geolocator = Nominatim(user_agent="wigle_tool")

def reverse_geocode(lat, lon, max_retries=3, delay_between_retries=5):
    retries = 0
    while retries < max_retries:
        try:
            location = geolocator.reverse((lat, lon), language="en", timeout=10)
            if location:
                return location.address
            return "Unknown Location"
        except Exception as e:
            print(color(f"[!] Error in reverse geocoding: {e}", Colors.WARNING))
            retries += 1
            if retries < max_retries:
                print(color(f"[!] Retrying in {delay_between_retries}s...", Colors.WARNING))
                time.sleep(delay_between_retries)
            else:
                print(color("[✗] Max retries reached. Moving to next location.", Colors.FAIL))
                return "Error during geocoding"
    return "Error during geocoding"

# === Load and Save Cache ===
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding="utf-8") as f:
        json.dump(cache, f, indent=4)

# === Parse Airodump CSV ===
def parse_airodump_csv(path, ssid_filter, first_time_after=None, last_time_before=None, first_time_before=None, last_time_after_filter=None):
    networks = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            ssid = row.get("ESSID", "").strip()
            bssid = row.get("BSSID", "").strip()
            first_time_str = row.get("FirstTime", "").strip()
            last_time_str = row.get("LastTime", "").strip()

            if not ssid or not bssid:
                continue

            try:
                first_time = datetime.strptime(first_time_str, "%a %b %d %H:%M:%S %Y") if first_time_str else None
                last_time = datetime.strptime(last_time_str, "%a %b %d %H:%M:%S %Y") if last_time_str else None
            except ValueError as e:
                print(color(f"[!] Warning: Failed to parse time for {ssid}: {e}", Colors.WARNING))
                continue

            # Time filtering
            if first_time_after and first_time and first_time < first_time_after:
                continue
            if first_time_before and first_time and first_time > first_time_before:
                continue
            if last_time_before and last_time and last_time > last_time_before:
                continue
            if last_time_after_filter and last_time and last_time < last_time_after_filter:
                continue

            if not ssid_filter or any(f.lower() in ssid.lower() for f in ssid_filter):
                networks.append({
                    "ssid": ssid,
                    "bssid": bssid
                })

    return networks

# === WiGLE SSID Search with Retry ===
def search_wigle(ssid, cache, country_code=None):
    if ssid in cache:
        print(color(f"[!] Using cached results for {ssid}", Colors.WARNING))
        return cache[ssid]

    url = "https://api.wigle.net/api/v2/network/search"
    headers = {
        "Authorization": f"Basic {WIGLE_API_KEY}",
        "Accept": "application/json"
    }

    results = []
    params = {
        "ssid": ssid,
        "resultsPerPage": 100,
        "first": 0
    }
    if country_code:
        params["countrycode"] = country_code.upper()

    try:
        page = 1
        while True:
            print(color(f"[*] Querying WiGLE for '{ssid}' - Page {page} (offset {params['first']})", Colors.OKCYAN))

            max_retries = 5
            retries = 0
            while retries < max_retries:
                resp = requests.get(url, headers=headers, params=params)
                status_code = resp.status_code
                print(f"    HTTP {status_code}")

                if status_code == 200:
                    break
                elif status_code == 429:
                    wait_time = 30
                    print(color(f"[!] Rate limited. Waiting {wait_time}s...", Colors.WARNING))
                    time.sleep(wait_time)
                elif 500 <= status_code < 600:
                    wait_time = (retries + 1) * 10
                    print(color(f"[!] Server error ({status_code}). Retrying after {wait_time}s...", Colors.WARNING))
                    time.sleep(wait_time)
                else:
                    print(color(f"[✗] Unexpected error {status_code}. Aborting search.", Colors.FAIL))
                    return []

                retries += 1

            if retries == max_retries:
                print(color(f"[✗] Max retries reached for {ssid}. Skipping...", Colors.FAIL))
                return []

            data = resp.json()

            if not data.get("success"):
                print(color(f"[✗] WiGLE query failed: {data.get('message')}", Colors.FAIL))
                break

            page_results = data.get("results", [])
            if not page_results:
                break

            for r in page_results:
                lat = r.get("trilat")
                lon = r.get("trilong")
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

        cache[ssid] = results
        save_cache(cache)
        print(color(f"[✓] Retrieved {len(results)} result(s) for {ssid}.", Colors.OKGREEN))

    except Exception as e:
        print(color(f"[✗] Exception querying {ssid}: {e}", Colors.FAIL))

    return results

# === Export to CSV ===
def export_csv(data, filename):
    # Use UTF-8 encoding to handle special characters
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ssid", "bssid", "lat", "lon", "address"])
        writer.writeheader()
        for row in data:
            # Reverse geocode the coordinates to get the address
            address = reverse_geocode(row["lat"], row["lon"])
            row["address"] = address
            writer.writerow(row)
            # Add delay between requests to the reverse geocoding API
            time.sleep(1)  # Introducing a 1-second delay between requests

# === Generate Map ===
def create_map(results, filename="wigle_map.html", use_clustering=True):
    if not results:
        print(color("[!] No results to plot.", Colors.WARNING))
        return

    start_coords = (results[0]["lat"], results[0]["lon"])
    m = folium.Map(location=start_coords, zoom_start=12)

    if use_clustering:
        cluster = MarkerCluster().add_to(m)
        for r in results:
            folium.Marker(
                location=[r["lat"], r["lon"]],
                popup=f"{r['ssid']} ({r['bssid']})",
                tooltip=r["ssid"]
            ).add_to(cluster)
    else:
        for r in results:
            folium.Marker(
                location=[r["lat"], r["lon"]],
                popup=f"{r['ssid']} ({r['bssid']})",
                tooltip=r["ssid"]
            ).add_to(m)

    m.save(filename)

# === Main ===
def main():
    global USE_COLORS

    parser = argparse.ArgumentParser(description="WiGLE SSID lookup tool")
    parser.add_argument("--ssid-filter", action="append", default=[], help="SSID(s) to filter (can be multiple)")
    parser.add_argument("--country-code", default=None, help="Country code for WiGLE filtering")
    parser.add_argument("--airodump-csv", default="capture.csv", help="Path to Airodump CSV file")
    parser.add_argument("--output-prefix", default="wigle_results", help="Prefix for output files")
    parser.add_argument("--first-time-after", help="Filter networks first seen after (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--last-time-before", help="Filter networks last seen before (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--first-time-before", help="Filter networks first seen before (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--last-time-after", help="Filter networks last seen after (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = parser.parse_args()

    if args.no_color:
        USE_COLORS = False

    first_time_after = datetime.strptime(args.first_time_after, "%Y-%m-%d %H:%M:%S") if args.first_time_after else None
    last_time_before = datetime.strptime(args.last_time_before, "%Y-%m-%d %H:%M:%S") if args.last_time_before else None
    first_time_before = datetime.strptime(args.first_time_before, "%Y-%m-%d %H:%M:%S") if args.first_time_before else None
    last_time_after_filter = datetime.strptime(args.last_time_after, "%Y-%m-%d %H:%M:%S") if args.last_time_after else None

    print(color("[*] Parsing Airodump CSV...", Colors.OKCYAN))
    ssids = parse_airodump_csv(
        args.airodump_csv,
        args.ssid_filter,
        first_time_after=first_time_after,
        last_time_before=last_time_before,
        first_time_before=first_time_before,
        last_time_after_filter=last_time_after_filter
    )

    print(color(f"[*] Found {len(ssids)} matching SSID(s).", Colors.OKCYAN))
    cache = load_cache()
    all_results = []

    for entry in ssids:
        print(color(f"[+] Searching WiGLE for SSID: {entry['ssid']}", Colors.OKBLUE))
        results = search_wigle(entry['ssid'], cache, country_code=args.country_code)
        if results:
            all_results.extend(results)
        time.sleep(1)

    if all_results:
        csv_filename = f"{args.output_prefix}.csv"
        html_filename = f"{args.output_prefix}.html"

        print(color("[*] Exporting to CSV...", Colors.OKCYAN))
        export_csv(all_results, csv_filename)

        print(color("[*] Generating map...", Colors.OKCYAN))
        create_map(all_results, filename=html_filename, use_clustering=USE_CLUSTERING)

        print(color("[✓] Done. Output files:", Colors.OKGREEN))
        print(color(f"    - {csv_filename}", Colors.OKGREEN))
        print(color(f"    - {html_filename}", Colors.OKGREEN))
    else:
        print(color("[!] No results to export.", Colors.WARNING))

if __name__ == "__main__":
    main()