"""Download the pinned, attributed LOTUS release used by BIO-GEN; verify with index_lotus.py."""
import json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'data/reference/lotus'

def main():
    FOLDER.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen('https://zenodo.org/api/records/19360665',timeout=60) as response:
        release=json.load(response)
    (FOLDER/'release.json').write_text(json.dumps(release,indent=2),encoding='utf-8')
    for f in release['files']:
        if f['key'].endswith('.csv.gz'):
            p=FOLDER/f['key']
            if p.exists() and p.stat().st_size==f['size']: continue
            temporary=p.with_suffix(p.suffix+'.part')
            print('Downloading',f['key'],flush=True)
            urllib.request.urlretrieve(f['links']['self'],temporary)
            if temporary.stat().st_size!=f['size']: raise ValueError('Incomplete file: '+f['key'])
            temporary.replace(p)
    print('Download complete. Run scripts/index_lotus.py to verify checksums and rebuild the index.')
if __name__=='__main__': main()
