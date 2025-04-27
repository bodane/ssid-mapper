# Code Use Case

The goal of this script is to locate 802.11b/g/a device locations (eg. phones/tablets/laptops with WiFi enabled), by using direct exports from `airodump-ng` using `.kismet.csv` extension files, without GPS data.

The kismet.csv file will contain captured 802.11b/g/a device probe requests with SSID information. This makes it possible to accurately attribute device location using this information. The accuracy of SSID locations is dependent on the accuracy of WiGLE.net information.

## Getting Started:

- You need a `airodump-ng` produced export in KISMET.CSV format (these are delimited with a semicolon), and contain more information that a typical CSV export.
- WiGLE.net API key *(a free registered account is fine if for personal use)*.

## Step 1: Install python, pip and dependencies.

```
apt update && apt install python3 pip
pip install -r requirements.txt
```

## Step 2: Create a local .env file

- Create your local `.env` file:

    ```
    WIGLE_API_KEY=your_api_key
    USE_CLUSTERING=true
    CACHE_FILE=wigle_cache.json  # File to store cached results
    ```

- Explanation of the configuration:
    - Enter your WiGLE.net encoded API key.
        - Log in at: https://wigle.net/account.
        - Scroll down to the API Key section.
        - Copy the value under: `Encoded for use: [THIS ONE]`

    - `USE_CLUSTERING=true` - Will group SSID's which are close to one another in a geo-location. This can be turned off if desired using `USE_CLUSTERING=false`.

    - `CACHE_FILE=wigle_cache.json` - Is a default and is used to store past queries. We then re-use this information to reduce API calls towards WiGLE.net. If it's believed the local cache is old, the cache entries for SSID's of interest can be cleared, or the file can be deleted to start from scratch and query the latest data from WiGLE.net.

## Step 3: Run script

```
chmod +x wigle_ssid_mapper.py
python3 wigle_ssid_mapper.py
```

### Results of running this script

At a minimum, the following files are produced provided defaults for filenames are used:

- `wigle_cache.json`: Contains a cached list of previous queries from Wigle.net. Will avoid unnecessary queries if we already have a local reference. Delete file or corresponding entries to ignore the cache and retrieve current results from Wigle.net.

- `wigle_results.csv`: Contains SSID, BSSID, latitude and longitude data from WiGLE including full address information for each SSID's location.

- `wigle_map.html`: An interactive map with markers showing the locations of the found SSIDs.

### Command Syntax:

```
python3 wigle_ssid_mapper.py -h

usage: wigle_ssid_mapper.py [-h] [--ssid-filter SSID_FILTER] [--country-code COUNTRY_CODE] [--airodump-csv AIRODUMP_CSV] [--output-prefix OUTPUT_PREFIX]
                            [--first-time-after FIRST_TIME_AFTER] [--last-time-before LAST_TIME_BEFORE] [--first-time-before FIRST_TIME_BEFORE] [--last-time-after LAST_TIME_AFTER]
                            [--no-color]

WiGLE SSID lookup tool

options:
  -h, --help            show this help message and exit
  --ssid-filter SSID_FILTER
                        SSID(s) to filter (can be multiple)
  --country-code COUNTRY_CODE
                        Country code for WiGLE filtering
  --airodump-csv AIRODUMP_CSV
                        Path to Airodump CSV file
  --output-prefix OUTPUT_PREFIX
                        Prefix for output files
  --first-time-after FIRST_TIME_AFTER
                        Filter networks first seen after (YYYY-MM-DD HH:MM:SS)
  --last-time-before LAST_TIME_BEFORE
                        Filter networks last seen before (YYYY-MM-DD HH:MM:SS)
  --first-time-before FIRST_TIME_BEFORE
                        Filter networks first seen before (YYYY-MM-DD HH:MM:SS)
  --last-time-after LAST_TIME_AFTER
                        Filter networks last seen after (YYYY-MM-DD HH:MM:SS)
  --no-color            Disable colored output
```

**NOTE**: For the "first-time-\*" and "last-time-\*" arguments, you may shorten the date syntax by using `YYYY-MM-DD` only without also appending `HH:MM:SS`. This would mean midnight, i.e `00:00:00`.

### Command usage example

- Use of all command arguments.

```
python3 wigle_ssid_mapper.py \
  --ssid-filter test \
  --country-code US \
  --airodump-csv capture.kismet.csv \
  --last-time-after "2025-04-25 19:07:00" \
  --last-time-before "2025-04-25 20:07:00" \
  --output-prefix test
```

- Use of no command arguments.
    - `--ssid-filter` (Optional) - Filtered to include an SSID of `test` only.
    - `--country-code` (Optional) - Default is any, we have set the US. If used, must be the two digit [ISO country code](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes). WiGLE.net does not strictly conform to API calls with the country code filter. We will still see other country results.
    - `--airodump-csv` (Optional) - Default output prefix is `capture.csv`, we are using `capture.kismet.csv`.   
    - `--last-time-after "2025-04-25 19:07:00"` and `--last-time-before "2025-04-25 20:07:00"` (Optional) - Specifies a timeframe of interest, for the last time probe requests were seen containing SSID's. `capture.kismet.csv` contains "FirstTime" and "LastTime" fields to make such filters possible.
    - `--output-prefix` (Optional) - Default is `wigle_map`. We have changed this to `test`.


```
python3 wigle_ssid_mapper.py
```

- Use of no command arguments.
    - `--ssid-filter` (Optional) - Default is everything in the CSV file.
    - `--country-code` (Optional) - Default is None, therefore any country. If used, must be the two digit [ISO country code](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes). WiGLE.net does not strictly conform to API calls with the country code filter. We will still see other country results.
    - `--airodump-csv` (Optional) - Default output prefix is `capture.csv`.
    - `--output-prefix` (Optional) - Default is `wigle_map`.