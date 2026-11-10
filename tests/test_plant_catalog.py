from fastapi.testclient import TestClient
from biogen.app import app
from biogen.plant_catalog import options,trained_labels,resolve,label_info
import pytest

def test_every_trained_label_has_exactly_one_dropdown_entry():
    entries=TestClient(app).get('/api/plant-options').json()
    labels=[label for entry in entries for label in entry['training_labels']]
    assert len(labels)==len(set(labels))==40
    assert set(labels)==set(trained_labels())
    assert all(entry['display_name'] and entry['common_names'] for entry in entries)

def test_familiar_labels_resolve_to_scientific_names_without_display_suffix():
    assert resolve('Aloe vera (Aloe Vera)')=='Aloe vera'
    assert resolve('Phyllanthus emblica (Amla)')=='Phyllanthus emblica'
    assert resolve('Pappaya')=='Carica papaya'
    assert label_info('Tulasi')['botanical_name']=='Ocimum tenuiflorum'
    assert label_info('Aloevera')['botanical_name']=='Aloe vera'

def test_broad_labels_are_present_without_silently_assigning_a_species():
    for label in ['Bamboo','Mint','Rose','Jasmine']:
        entry=label_info(label)
        assert entry['requires_scientific_confirmation']
        with pytest.raises(ValueError):resolve(entry['display_name'])
    assert resolve('Mentha spicata')=='Mentha spicata'

def test_reference_profiles_are_retained_and_separately_marked():
    entries=options()
    galangal=next(p for p in entries if p['botanical_name']=='Alpinia galanga')
    assert galangal['reference_profile'] and not galangal['trained']
    assert sum(bool(p['reference_profile']) for p in entries)==30
