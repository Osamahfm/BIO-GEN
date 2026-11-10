"""Prepare a complete COCONUT fallback for a scientific name; use cached results offline afterward."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from biogen.coconut import get_records
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('scientific_name');a=p.parse_args()
    records,coverage=get_records(a.scientific_name)
    print(json.dumps(coverage,indent=2),flush=True)
    print('Exact-species records:',len(records),flush=True)
    if not coverage['complete']:raise SystemExit(1)
