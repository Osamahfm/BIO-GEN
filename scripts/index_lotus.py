"""Index the entire downloaded LOTUS release, retaining every occurrence and reference."""
import csv,gzip,hashlib,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'data/reference/lotus'

def build():
    release=json.loads((FOLDER/'release.json').read_text(encoding='utf-8'))
    for f in release['files']:
        if f['key'].endswith('.csv.gz'):
            p=FOLDER/f['key']
            if p.stat().st_size!=f['size']: raise ValueError('Incomplete download: '+p.name)
            if f.get('checksum','').startswith('md5:'):
                h=hashlib.md5()
                with p.open('rb') as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
                if h.hexdigest()!=f['checksum'].split(':',1)[1]: raise ValueError('Checksum failed: '+p.name)
    target=FOLDER/'lotus-building.sqlite3'
    with sqlite3.connect(target) as con:
        con.execute('DROP TABLE IF EXISTS occurrences');con.execute('DROP TABLE IF EXISTS structures')
        con.execute('CREATE TABLE occurrences(inchikey TEXT,name TEXT,normalized_name TEXT,taxon TEXT,doi TEXT,reference TEXT,validation TEXT)')
        con.execute('CREATE TABLE structures(inchikey TEXT PRIMARY KEY,smiles TEXT,name TEXT,cid TEXT,wikidata TEXT)')
        count=0;batch=[]
        with gzip.open(FOLDER/'260413_frozen.csv.gz','rt',encoding='utf-8',newline='') as stream:
            for r in csv.DictReader(stream):
                n=r.get('organism_name','')
                batch.append((r['structure_inchikey'],n,' '.join(n.casefold().split()),r.get('organism_wikidata',''),r.get('reference_doi',''),r.get('reference_wikidata',''),r.get('manual_validation','')))
                if len(batch)>=10000:
                    con.executemany('INSERT INTO occurrences VALUES (?,?,?,?,?,?,?)',batch);count+=len(batch);batch=[]
            con.executemany('INSERT INTO occurrences VALUES (?,?,?,?,?,?,?)',batch);count+=len(batch)
        print('Occurrence rows:',count,flush=True);batch=[]
        with gzip.open(FOLDER/'260413_frozen_metadata.csv.gz','rt',encoding='utf-8',newline='') as stream:
            for r in csv.DictReader(stream):
                def clean(k):
                    v=r.get(k,'')
                    return '' if v in ('NA','NaN','nan') else v
                key=clean('structure_inchikey')
                if not key: continue
                batch.append((key,clean('structure_smiles'),clean('structure_nameTraditional') or clean('structure_nameIupac'),clean('structure_cid'),clean('structure_wikidata')))
                if len(batch)>=10000:
                    con.executemany('INSERT OR IGNORE INTO structures VALUES (?,?,?,?,?)',batch);batch=[]
            con.executemany('INSERT OR IGNORE INTO structures VALUES (?,?,?,?,?)',batch)
        con.execute('CREATE INDEX organism_name_idx ON occurrences(normalized_name)')
        con.execute('CREATE INDEX organism_taxon_idx ON occurrences(taxon)')
        con.execute('CREATE INDEX occurrence_structure_idx ON occurrences(inchikey)')
        stats={'ready':True,'release':'LOTUS 2026-04-13','record_id':str(release['id']),'doi':'https://doi.org/10.5281/zenodo.'+str(release['id']),'license':release['metadata']['license']['id'],'occurrences':count,'unique_structures':con.execute('SELECT COUNT(*) FROM structures').fetchone()[0],'organism_labels':con.execute('SELECT COUNT(DISTINCT normalized_name) FROM occurrences').fetchone()[0],'plant_part_available':False,'download_checksums_verified':True}
        con.commit()
    con.close()
    target.replace(FOLDER/'lotus.sqlite3')
    (FOLDER/'index-status.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
    print(json.dumps(stats,indent=2),flush=True)

if __name__=='__main__': build()
