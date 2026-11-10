from biogen.chemistry import discover,analyse_compounds
from biogen.plant_compounds import retrieve

def test_full_species_lookup_and_preserved_evidence():
    r=discover('Ocimum tenuiflorum','leaves')
    assert len(r['compounds'])>100
    assert r['coverage']['database']['download_checksums_verified']
    assert len(r['compounds'])==r['coverage']['species_structures']
    assert all(c['selected'] for c in r['compounds'])
    assert r['part_supported_structures']==5
    assert sum(len(c.get('references',[])) for c in r['compounds'])>=r['coverage']['species_occurrence_records']

def test_new_species_and_explicit_synonym():
    neem,c=retrieve('Azadirachta indica','leaves')
    assert len(neem)>400
    assert c['matched_database_names']==['Azadirachta indica']
    _,first=retrieve('Ocimum tenuiflorum','leaves')
    _,second=retrieve('Ocimum sanctum','leaves')
    assert first['species_structures']==second['species_structures']>5

def test_optional_filters_keep_complete_results():
    a=discover('Ocimum tenuiflorum','leaves',max_mw=200)
    b=discover('Ocimum tenuiflorum','leaves',max_mw=200,apply_property_filters=True)
    assert len(a['compounds'])==len(b['compounds'])
    assert all(c['selected'] for c in a['compounds'])
    assert sum(c['selected'] for c in b['compounds'])<len(b['compounds'])
    assert any(not c['selected'] and c['exclusion_reasons'] for c in b['compounds'])

def test_duplicate_merge_retains_part_support_and_both_sources():
    a={'name':'Ethanol','smiles':'CCO','part_status':'unverified','references':[{'source_url':'https://example.org/one'}]}
    b={'name':'Ethyl alcohol','smiles':'OCC','plant_part':'leaves','part_status':'reported_for_selected_part','references':[{'source_url':'https://example.org/two'}]}
    r=analyse_compounds([a,b])
    assert len(r['compounds'])==1
    assert len(r['compounds'][0]['references'])==2
    assert r['compounds'][0]['part_status']=='reported_for_selected_part'
    assert r['compounds'][0]['plant_part']=='leaves'

def test_unanalysed_records_retain_source():
    r=analyse_compounds([{'name':'Unknown','smiles':'','references':[{'source_url':'https://example.org/evidence'}]}])
    assert not r['compounds']
    assert r['invalid'][0]['references'][0]['source_url']=='https://example.org/evidence'
