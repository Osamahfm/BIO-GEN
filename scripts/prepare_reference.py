"""Download public molecular structures; curate associations independently of IMPPAT data."""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
NAMES = {3314: 'Eugenol', 5281792: 'Rosmarinic acid', 64945: 'Ursolic acid',
         5280443: 'Apigenin', 6549: 'Linalool'}
URL = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/' + ','.join(map(str, NAMES)) + '/property/IsomericSMILES,IUPACName/JSON'


def main():
    with urllib.request.urlopen(URL, timeout=60) as response:
        raw = json.load(response)
    records = []
    for p in raw['PropertyTable']['Properties']:
        cid = p['CID']
        primary = cid in (3314, 5281792)
        records.append({'name': NAMES[cid], 'cid': cid, 'scientific_name': 'Ocimum tenuiflorum',
                        'plant_part': 'leaves', 'smiles': p['SMILES'],
                        'source_url': 'https://pubmed.ncbi.nlm.nih.gov/42064634/' if primary else 'https://pmc.ncbi.nlm.nih.gov/articles/PMC11521583/',
                        'structure_source': f'https://pubchem.ncbi.nlm.nih.gov/compound/{cid}',
                        'evidence_note': 'HPLC measurements reported in a Tulsi leaf elicitation study; not measured in this specimen.' if primary else 'Association reported in a phytochemical review; primary evidence should be checked before advancing.',
                        'evidence_type': 'published experimental assay' if primary else 'review-reported association',
                        'retrieved_at': datetime.now(timezone.utc).isoformat()})
    folder = ROOT / 'data/reference'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'pubchem-response.json').write_text(json.dumps(raw, indent=2), encoding='utf-8')
    (folder / 'compounds.json').write_text(json.dumps({'source': 'BIO-GEN independently curated demonstration records; not an IMPPAT database export', 'structure_api': URL, 'records': records}, indent=2), encoding='utf-8')
    print(f'Prepared {len(records)} referenced structures.')


if __name__ == '__main__':
    main()
