# Code Use Case

The goal of this script is to locate 802.11b/g/a device locations (eg. phones/tablets/laptops with WiFi enabled), by using direct exports from `airodump-ng` using `.netxml` extension files, without GPS data.

The kismet.netxml files will contain captured 802.11b/g/a device probe requests with SSID information. This makes it possible to attribute all past locations a device has previously been seen, based on it's past Wi-Fi network associations. The accuracy of SSID locations is dependent on the accuracy of WiGLE.net information.

## Getting Started:

- You need a `airodump-ng` produced export in NETXML format (this is a XML formatted file).
- WiGLE.net API key *(a free registered account is fine if for personal use)*.

## Step 1: Install python, pip and dependencies.

```
apt update && apt install python3 pip
pip install -r requirements.txt
```

## Step 2: Create a local .env file

- Create your local `.env` file. Use the below information to get started:

    ```
    WIGLE_API_KEY=your_api_key
    USE_CLUSTERING=true
    CACHE_FILE=wigle_cache.json  # File to store cached results
    ```

- Explanation of the configuration:
    - `WIGLE_API_KEY=your_api_key` - Enter your WiGLE.net encoded API key.
        - Log in at: https://wigle.net/account.
        - Scroll down to the API Key section.
        - Copy the value under: `Encoded for use: [THIS ONE]`

    - `USE_CLUSTERING=true` - Will group SSID's which are close to one another in a geo-location. This can be turned off if desired using `USE_CLUSTERING=false`.

    - `CACHE_FILE=wigle_cache.json` - Is a default and is used to store past queries. We then re-use this information to reduce API calls towards WiGLE.net. If it's believed the local cache is old, the cache entries for SSID's of interest can be cleared, or the file can be deleted to start from scratch and query the latest data from WiGLE.net.

## Step 3: Run script

- Give permission to execute.
    ```
    chmod +x wigle_ssid_mapper.py
    ```

- Run script
    ```
    python3 .\wigle_ssid_mapper.py -h
    usage: wigle_ssid_mapper.py [-h] [--netxml NETXML] [--ssid SSID] [--country-code COUNTRY_CODE] [--output-prefix OUTPUT_PREFIX] [--first-time FIRST_TIME [FIRST_TIME ...]]
                                [--last-time LAST_TIME [LAST_TIME ...]] [--no-color] [--debug]

    WiGLE SSID lookup tool (OOP version)

    options:
    -h, --help            show this help message and exit
    --netxml NETXML       Airodump-ng netxml file
    --ssid SSID           Direct SSID to search
    --country-code COUNTRY_CODE
    --output-prefix OUTPUT_PREFIX
    --first-time FIRST_TIME [FIRST_TIME ...]
                            1 or 2 'first-time' values
    --last-time LAST_TIME [LAST_TIME ...]
                            1 or 2 'last-time' values
    --no-color
    --debug
    ```

    **NOTE**: For the "first-time" and "last-time" arguments, the time format is `YYYY-MM-DD HH:MM`.

### Command usage example

- Use of all command arguments when filtering based on time.

    ```
    python3 wigle_ssid_mapper.py \
    --country-code US \
    --netxml capture.kismet.netxml \
    --last-time "2025-04-25 19:07" "2025-04-25 20:07" \
    --output-prefix test
    ```

    - `--country-code` (Optional) - Default is any. We have set the US. If used, must be the two digit [ISO country code](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes). WiGLE.net does not strictly conform to API calls with the country code filter. We will still see other country results.
    - `--netxml` (Optional) - We are using `capture.kismet.netxml`.   
    - `--last-time "2025-04-25 19:07" "2025-04-25 20:07"` (Optional) - Specifies a timeframe of interest, for the last time probe requests were seen containing SSID's.
    - `--output-prefix` (Optional) - Default is `wigle_results`. We have changed this to `test`.



- Use of only the --ssid command argument.

    ```
    python3 wigle_ssid_mapper.py --ssid test
    ```

    - `--ssid` (Optional) - Will bypass used of --netxml and perform a direct lookup of an SSID on WiGLE.net.
    - `--country-code` (Optional) - Default is None, therefore any country. If used, must be the two digit [ISO country code](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes). WiGLE.net does not strictly conform to API calls with the country code filter. We will still see other country results.
    - `--output-prefix` (Optional) - Default is `wigle_map`.

### Results of running this script

At a minimum, the following files are produced provided defaults for filenames are used:

- `wigle_cache.json`: Contains a cached list of previous queries from Wigle.net. Will avoid unnecessary queries if we already have a local reference. Delete file or corresponding entries to ignore the cache and retrieve current results from Wigle.net.

- `wigle_results.csv`: Contains SSID, BSSID, latitude and longitude data from WiGLE including full address information for each SSID's location.

- `wigle_map.html`: An interactive map with markers showing the locations of the found SSIDs.

