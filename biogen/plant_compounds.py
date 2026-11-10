"""Retrieve every matching documented LOTUS occurrence without a result cap."""
import json
import sqlite3
from urllib.parse import quote
from .settings import ROOT

FOLDER=ROOT/'data/reference/lotus'
DATABASE=FOLDER/'lotus.sqlite3'
SYNONYMS={'ocimum tenuiflorum':['ocimum sanctum'],'ocimum sanctum':['ocimum tenuiflorum'], 'citrus limon':['citrus × limon','citrus x limon','citrus ×limon'], 'citrus × limon':['citrus limon'], 'citrus x limon':['citrus limon'], 'citrus ×limon':['citrus limon']}

def normalized(text):
    return ' '.join(text.casefold().split())

def status():
    p=FOLDER/'index-status.json'
    return json.loads(p.read_text(encoding='utf-8')) if DATABASE.exists() and p.exists() else {'ready':False,'message':'LOTUS database is not installed.'}

def retrieve(scientific_name,plant_part,include_part_unverified=True,refresh_external=False):
    info=status()
    names=[normalized(scientific_name)]+SYNONYMS.get(normalized(scientific_name),[])
    records=[];matched_names=[];occurrence_count=0;grouped={}
    if info.get('ready'):
        with sqlite3.connect(DATABASE) as con:
            marks=','.join('?' for _ in names)
            taxons=[r[0] for r in con.execute(f'SELECT DISTINCT taxon FROM occurrences WHERE normalized_name IN ({marks}) AND taxon!=""',names)]
            conditions=[f'o.normalized_name IN ({marks})'];params=list(names)
            if taxons:
                conditions.append('o.taxon IN ('+','.join('?' for _ in taxons)+')');params.extend(taxons)
            rows=con.execute('SELECT o.inchikey,o.name,o.doi,o.reference,o.taxon,o.validation,s.smiles,s.name,s.cid,s.wikidata FROM occurrences o LEFT JOIN structures s ON s.inchikey=o.inchikey WHERE '+' OR '.join(conditions),params).fetchall()
        occurrence_count=len(rows);matched_names=sorted({r[1] for r in rows})
        for key,organism,doi,reference,taxon,validation,smiles,name,cid,wikidata in rows:
            url='https://doi.org/'+quote(doi,safe='/():;.-_') if doi else reference
            evidence={'source':'LOTUS','source_url':url,'reported_species':organism,'plant_part':None,'part_status':'unverified','taxon_url':taxon,'source_validation':validation,'release':info.get('release')}
            if key not in grouped:
                grouped[key]={'name':name or key,'scientific_name':scientific_name,'plant_part':None,'part_status':'unverified','smiles':smiles or '','inchikey':key,'cid':cid or None,'source_url':url,'structure_source':'https://pubchem.ncbi.nlm.nih.gov/compound/'+str(cid) if cid else wikidata or '','evidence_type':'database-reported species occurrence','evidence_note':'Reported for this species in LOTUS. Plant part is not supplied by this release; presence in this specimen is unconfirmed.','references':[]}
            if evidence not in grouped[key]['references']:
                grouped[key]['references'].append(evidence)
        if include_part_unverified:
            records.extend(grouped.values())
    fallback=None
    if not grouped and include_part_unverified:
        from .coconut import get_records
        additional,fallback=get_records(scientific_name,refresh=refresh_external)
        records.extend(additional)
        matched_names=sorted(set(matched_names+[r['reported_species'] for record in additional for r in record.get('references',[])]))
    local=json.loads((ROOT/'data/reference/compounds.json').read_text(encoding='utf-8'))['records']
    local=[r for r in local if normalized(r['scientific_name']) in names and normalized(r['plant_part'])==normalized(plant_part)]
    for r in local:
        records.append(dict(r,part_status='reported_for_selected_part',references=[{'source':'Curated reference','source_url':r['source_url'],'reported_species':r['scientific_name'],'plant_part':r['plant_part'],'part_status':'reported_for_selected_part','evidence_type':r.get('evidence_type','')}]))
    return records,{'database':info,'queried_species':scientific_name,'queried_part':plant_part,'matched_database_names':matched_names,'species_occurrence_records':occurrence_count,'species_structures':len(grouped) if grouped else len({r.get('inchikey') or r.get('coconut_id') for r in records if r.get('coconut_id')}),'part_specific_curated_records':len(local),'include_part_unverified':include_part_unverified,'retrieval_complete_for_query':bool(info.get('ready')) and (fallback is None or bool(fallback.get('complete'))),'fallback':fallback,'scope':'Full LOTUS species lookup, COCONUT fallback where LOTUS has no species records, and curated part-specific references; not a complete specimen assay.','warnings':([] if info.get('ready') else ['LOTUS unavailable; installed-source coverage is incomplete.'])+(fallback.get('warnings',[]) if fallback else [])}
