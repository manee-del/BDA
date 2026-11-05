"""Optional real API collection, separate from historical replay. No scheduler is installed."""
import argparse
import datetime as dt
import json
import logging
import os
from pathlib import Path
import sqlite3
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data' / 'incoming'
DEST.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=DEST / 'collection.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def collect():
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    sources = [('weather', 'https://api.open-meteo.com/v1/forecast', {
        'latitude': 28.6139, 'longitude': 77.2090, 'timezone': 'Asia/Kolkata',
        'hourly': 'temperature_2m,relative_humidity_2m,wind_speed_10m', 'forecast_days': 1,
    })]
    key = os.environ.get('DATA_GOV_API_KEY')
    if key:
        sources.append(('pollution', 'https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69', {
            'api-key': key, 'format': 'json', 'limit': 1000, 'filters[state]': 'Delhi',
        }))
    else:
        print('DATA_GOV_API_KEY is absent: collecting weather only. No pollution values will be fabricated.')
    with sqlite3.connect(DEST / 'snapshots.sqlite') as db:
        db.execute('CREATE TABLE IF NOT EXISTS snapshots (source TEXT, digest TEXT, fetched_at TEXT, payload TEXT, PRIMARY KEY(source,digest))')
        for source, url, params in sources:
            try:
                response = requests.get(url, params=params, timeout=60)
                response.raise_for_status()
                payload = response.json()
                if source == 'pollution' and not payload.get('records'):
                    raise ValueError('Provider returned no pollution records')
                import hashlib
                serialized = json.dumps(payload, sort_keys=True)
                digest = hashlib.sha256(serialized.encode()).hexdigest()
                db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?)', (source, digest, now, serialized))
                (DEST / f'{source}_{digest[:16]}.json').write_text(serialized, encoding='utf-8')
                logging.info('%s collected at %s', source, now)
                print(source, 'saved successfully')
            except Exception as exc:
                # Do not log request URLs: the pollution URL contains the API key.
                logging.error('%s failed: %s', source, type(exc).__name__)
                print(source, 'failed:', type(exc).__name__)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Collect once; otherwise repeat every hour while this process runs.')
    args = parser.parse_args()
    while True:
        collect()
        if args.once:
            break
        time.sleep(3600)
