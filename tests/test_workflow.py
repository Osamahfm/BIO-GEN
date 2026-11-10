"""Exercise actual adapters and persistent transitions; no mocked prediction values."""
import io
import json
import os
from pathlib import Path
import tempfile

# Store isolation is established before imports by conftest.py.

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from biogen.app import app
from biogen.chemistry import analyse_compounds
from biogen import store

client = TestClient(app)


def make_case():
    return client.post('/api/cases', data={'title': 'Verification case'}).json()


def upload(c, colour='green', size=(400, 400)):
    image = Image.new('RGB', size, 'white')
    from PIL import ImageDraw
    ImageDraw.Draw(image).ellipse((80, 30, 320, 370), fill=colour)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return client.post(f'/api/cases/{c["id"]}/image', data={'revision': c['revision']}, files={'file': ('specimen.png', buffer.getvalue(), 'image/png')}).json()


def confirm(c, name='Ocimum tenuiflorum', part='leaves'):
    return client.post(f'/api/cases/{c["id"]}/profile', json={'revision': c['revision'],
        'scientific_name': name, 'plant_part': part, 'target_disease': 'Research indication',
        'researcher': 'Test researcher', 'identity_basis': 'Test specimen label',
        'source_url': 'https://example.org/reference'}).json()


def test_connected_case_history_and_exports():
    c0 = make_case()
    assert c0['stage'] == 'C0'
    c1 = confirm(upload(c0))
    assert c1['stage'] == 'C1'
    c2r = client.post(f'/api/cases/{c1["id"]}/quality', json={'revision': c1['revision']})
    assert c2r.status_code == 200, c2r.text
    c2 = c2r.json()
    assert c2['profile'] == c1['profile']
    assert c2['quality']['metrics']['plantcv_observation_fields']
    c3r = client.post(f'/api/cases/{c1["id"]}/discovery', json={'revision': c2['revision']})
    assert c3r.status_code == 200, c3r.text
    c3 = c3r.json()
    assert c3['stage'] == 'C3'
    assert c3['quality'] == c2['quality']
    assert len(c3['discovery']['compounds']) > 100
    assert c3['discovery']['coverage']['database']['ready']
    eugenol = next(r for r in c3['discovery']['compounds'] if r['name'] == 'Eugenol')
    assert eugenol['descriptors']['mw'] == pytest.approx(164.2, abs=.1)
    assert eugenol['descriptors']['formula'] == 'C10H12O2'
    assert client.get(f'/api/cases/{c3["id"]}/compounds.csv').status_code == 200
    exported = client.get(f'/api/cases/{c3["id"]}/export.json').json()
    assert exported['history'][0]['stage'] == 'C0'
    assert store.get(c3['id'], 0) == c0
    assert 'BIO-GEN research case' in client.get(f'/api/cases/{c3["id"]}/report').text
    assert store.get(c3['id']) == c3


def test_prerequisites_stale_updates_and_invalid_image():
    c = make_case()
    assert client.post(f'/api/cases/{c["id"]}/discovery', json={'revision': 0}).status_code == 422
    assert client.post(f'/api/cases/{c["id"]}/quality', json={'revision': 0}).status_code == 422
    assert client.post(f'/api/cases/{c["id"]}/image', data={'revision': 0}, files={'file': ('bad.png', b'not an image')}).status_code == 422
    c1 = confirm(upload(c))
    assert client.post(f'/api/cases/{c["id"]}/quality', json={'revision': 0}).status_code == 409
    assert client.get('/api/cases/missing').status_code == 404
    assert client.get('/api/images/invalid.jpg').status_code == 404


def test_missing_evidence_is_not_invented_and_part_specific():
    from biogen.chemistry import discover
    assert discover('Unknown species', 'leaves')['compounds'] == []
    assert discover('Ocimum tenuiflorum', 'root', include_part_unverified=False)['compounds'] == []
    assert len(discover('Ocimum tenuiflorum', 'root')['compounds']) > 100
    assert discover('Unknown species', 'leaves')['evidence_gaps']


def test_invalid_smiles_duplicates_and_filtering():
    rows = [{'name': 'Ethanol', 'smiles': 'CCO'}, {'name': 'Same ethanol', 'smiles': 'OCC'},
            {'name': 'Invalid', 'smiles': 'not-smiles'}]
    result = analyse_compounds(rows, max_mw=40)
    assert len(result['compounds']) == 1
    assert result['duplicates'] == ['Same ethanol']
    assert result['invalid'][0]['name'] == 'Invalid'
    assert not result['compounds'][0]['selected']


def test_blank_image_flags_hold_recommendations_and_review_is_not_override():
    c = make_case()
    image = io.BytesIO()
    Image.new('RGB', (400, 400), 'white').save(image, 'PNG')
    c = client.post(f'/api/cases/{c["id"]}/image', data={'revision': c['revision']}, files={'file': ('blank.png', image.getvalue())}).json()
    c = confirm(c)
    c = client.post(f'/api/cases/{c["id"]}/quality', json={'revision': c['revision']}).json()
    assert any(f['critical'] for f in c['quality']['flags'])
    c = client.post(f'/api/cases/{c["id"]}/discovery', json={'revision': c['revision']}).json()
    assert c['discovery']['recommendations_held']
    body = {'revision': c['revision'], 'reviewer': 'Researcher', 'role': 'Plant scientist',
            'outcome': 'evidence_supported', 'note': 'Reviewed the specimen and documented the remaining limitations.'}
    assert client.post(f'/api/cases/{c["id"]}/reviews', json=body).status_code == 422
    body['source_url'] = 'https://example.org/evidence'
    c = client.post(f'/api/cases/{c["id"]}/reviews', json=body).json()
    assert c['discovery']['recommendations_held']
    assert c['reviews'][0]['stage'] == 'C3'


def test_upstream_changes_invalidate_downstream_results():
    c = confirm(upload(make_case()))
    c = client.post(f'/api/cases/{c["id"]}/quality', json={'revision': c['revision']}).json()
    c = client.post(f'/api/cases/{c["id"]}/discovery', json={'revision': c['revision']}).json()
    changed = confirm(c, part='root')
    assert changed['quality'] is None and changed['discovery'] is None
    assert changed['stage'] == 'C1'
    replaced = upload(changed)
    assert not replaced['profile'].get('confirmed')
    assert replaced['stage'] == 'C0'


def test_actual_ayur_retrieval():
    plants = client.get('/api/plants?q=Ocimum').json()
    assert any(p['botanical_name'] == 'Ocimum tenuiflorum' for p in plants)


def test_report_escapes_user_content():
    c = client.post('/api/cases', data={'title': '<script>alert(1)</script>'}).json()
    report = client.get(f'/api/cases/{c["id"]}/report').text
    assert '<script>alert(1)</script>' not in report
    assert '&lt;script&gt;' in report

def test_label_only_case_can_save_and_run_quality_without_guessing_species():
    c1=confirm(upload(make_case()),name='Bamboo')
    assert c1['stage']=='C1'
    assert c1['profile']['confirmed']
    assert c1['profile']['species_confirmed'] is False
    assert c1['profile']['scientific_name']==''
    assert c1['profile']['plant_label']=='Bamboo'
    response=client.post(f'/api/cases/{c1["id"]}/quality',json={'revision':c1['revision']})
    assert response.status_code==200,response.text
    c2=response.json()
    assert c2['stage']=='C2'
    blocked=client.post(f'/api/cases/{c2["id"]}/discovery',json={'revision':c2['revision']})
    assert blocked.status_code==422
    assert 'exact scientific species' in blocked.json()['detail']
    assert store.get(c2['id'])['discovery'] is None
    report=client.get(f'/api/cases/{c2["id"]}/report').text
    assert 'Unconfirmed — training label only' in report
    reopened=client.get(f'/api/cases/{c2["id"]}').json()
    assert reopened['profile']['plant_label']=='Bamboo'

def test_confirming_species_later_updates_identity_and_invalidates_quality():
    c1=confirm(upload(make_case()),name='Mint')
    c2=client.post(f'/api/cases/{c1["id"]}/quality',json={'revision':c1['revision']}).json()
    updated=confirm(c2,name='Mentha spicata')
    assert updated['profile']['species_confirmed']
    assert updated['profile']['scientific_name']=='Mentha spicata'
    assert updated['quality'] is None and updated['discovery'] is None
    assert store.history(c1['id'])[-2]['profile']['species_confirmed'] is False
