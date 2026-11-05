"""Download the six original, CC BY 4.0 Delhi station files with checksum validation."""
import hashlib
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data' / 'raw'
DEST.mkdir(parents=True, exist_ok=True)
API = 'https://data.mendeley.com/public-api/datasets/bzhzr9b64v/files?folder_id=root&version=1'
response = requests.get(API, timeout=60)
response.raise_for_status()
files = response.json()
for entry in files:
    name = entry['filename']
    if Path(name).name != name or not name.endswith('.csv'):
        raise ValueError('Unexpected dataset filename')
    target = DEST / name
    expected = entry['content_details']['sha256_hash']
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        response = requests.get(entry['content_details']['download_url'], timeout=120)
        response.raise_for_status()
        payload = response.content
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError('Checksum mismatch: ' + name)
        target.write_bytes(payload)
    print(name, target.stat().st_size, 'bytes verified', flush=True)
(ROOT / 'data' / 'source_manifest.json').write_text(json.dumps({
    'title': 'Delhi Multi-Site Air-Quality Data Set',
    'authors': ['Shilpa Sonawani', 'Kailas Patil'],
    'doi': '10.17632/bzhzr9b64v.1',
    'source': 'https://data.mendeley.com/datasets/bzhzr9b64v/1',
    'license': 'CC BY 4.0', 'files': files,
}, indent=2), encoding='utf-8')
