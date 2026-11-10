"""Add independently sourced association records from CSV; do not import restricted data."""
import argparse
import csv
import json
from pathlib import Path
from rdkit import Chem

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ['name', 'scientific_name', 'plant_part', 'smiles', 'source_url', 'structure_source', 'evidence_note']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file', type=Path)
    args = parser.parse_args()
    with args.csv_file.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not set(REQUIRED).issubset(reader.fieldnames or []):
            raise ValueError('CSV requires: ' + ', '.join(REQUIRED))
        rows = list(reader)
    for i, row in enumerate(rows, 2):
        if not all(row[x].strip() for x in REQUIRED):
            raise ValueError(f'Row {i} has a missing required field')
        if not all(row[x].startswith(('http://', 'https://')) for x in ['source_url', 'structure_source']):
            raise ValueError(f'Row {i} requires evidence and structure URLs')
        if Chem.MolFromSmiles(row['smiles']) is None:
            raise ValueError(f'Row {i} has invalid SMILES')
    target = ROOT / 'data/reference/compounds.json'
    catalog = json.loads(target.read_text(encoding='utf-8'))
    catalog['records'].extend(rows)
    target.write_text(json.dumps(catalog, indent=2), encoding='utf-8')
    print(f'Added {len(rows)} records. Duplicate structures are removed per case at analysis time.')


if __name__ == '__main__':
    main()
