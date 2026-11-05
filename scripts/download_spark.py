"""Resumable, checksum-verified download of Spark's official PyPI distribution."""
import concurrent.futures
import hashlib
from pathlib import Path
import time
import requests

root = Path(__file__).resolve().parents[1]
dest = root / 'cluster' / 'packages'
dest.mkdir(exist_ok=True)
for package, version in [('pyspark', '3.5.7'), ('py4j', '0.10.9.7')]:
    r = requests.get(f'https://pypi.org/pypi/{package}/{version}/json', timeout=60)
    r.raise_for_status()
    candidates = r.json()['urls']
    entry = next((f for f in candidates if f['filename'].endswith('py2.py3-none-any.whl')), candidates[0])
    target = dest / entry['filename']
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == entry['digests']['sha256']:
        print(target.name, 'already verified', flush=True)
        continue
    size = entry['size']
    block = 8 * 1024 * 1024
    parts = list(range((size + block - 1) // block))

    def get_part(i):
        start, end = i * block, min(size - 1, (i + 1) * block - 1)
        part = dest / (target.name + f'.part{i}')
        if part.exists() and part.stat().st_size == end - start + 1:
            return part
        for attempt in range(5):
            try:
                reply = requests.get(entry['url'], headers={'Range': f'bytes={start}-{end}'}, timeout=(20, 120))
                reply.raise_for_status()
                if len(reply.content) != end - start + 1:
                    raise ValueError('Unexpected byte range length')
                part.write_bytes(reply.content)
                print(f'{package}: part {i+1}/{len(parts)}', flush=True)
                return part
            except requests.RequestException:
                if attempt == 4:
                    raise
                time.sleep(2)
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        downloaded = list(pool.map(get_part, parts))
    with target.open('wb') as stream:
        for part in downloaded:
            stream.write(part.read_bytes())
    if hashlib.sha256(target.read_bytes()).hexdigest() != entry['digests']['sha256']:
        raise ValueError('Package checksum mismatch')
    print(target.name, 'verified', flush=True)
    for part in downloaded:
        part.unlink()
