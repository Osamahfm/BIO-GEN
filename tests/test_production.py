from test_workflow import client, confirm, make_case, upload


def test_production_uses_c3_and_invalidates_when_inputs_change():
    case = make_case()
    url = f'/api/cases/{case["id"]}'
    assert client.post(url + '/production', json={'revision': 0}).status_code == 422
    case = confirm(upload(case))
    quality = client.post(url + '/quality', json={'revision': case['revision']})
    assert quality.status_code == 200, quality.text
    discovery = client.post(url + '/discovery', json={'revision': quality.json()['revision']})
    assert discovery.status_code == 200, discovery.text
    c3 = discovery.json()
    config = client.get(url + '/production').json()
    assert config['available'], config['reason']
    assert config['target']['name'].casefold() == 'eugenol'
    assert config['target']['part_status'] == 'reported_for_selected_part'
    result = client.post(url + '/production', json={'revision': c3['revision']})
    assert result.status_code == 200, result.text
    c4 = result.json()
    assert c4['stage'] == 'C4'
    assert c4['discovery'] == c3['discovery']
    simulation = c4['production']
    assert simulation['input_revision'] == c3['revision']
    assert [row['flux'] for row in simulation['scenarios']] == [6, 3, 0, 10]
    assert [row['low_supply_flux'] for row in simulation['scenarios']] == [4, 3, 0, 4]
    assert simulation['recommendations_held']
    assert 'EGS1 knockout' in client.get(url + '/report').text
    assert client.post(url + '/production', json={'revision': c3['revision']}).status_code == 409
    changed = confirm(c4, part='root')
    assert changed['stage'] == 'C1'
    assert changed['production'] is None
    assert client.get(url + '/export.json').json()['history'][-2]['production'] == simulation
