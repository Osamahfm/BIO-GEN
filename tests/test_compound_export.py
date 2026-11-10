import csv,io
from fastapi.testclient import TestClient
from biogen.app import app
from biogen import store

def test_csv_keeps_unanalysed_records_with_their_references():
    c=store.create({'title':'Export verification'})
    d={'compounds':[],'invalid':[{'name':'Unresolved compound','source_url':'https://example.org/source','references':[{'source_url':'https://example.org/source'}],'reason':'No structure'}],'filters':{'applied':False},'recommendations_held':False}
    c=store.update(c['id'],0,{'discovery':d},'Export verification')
    response=TestClient(app).get('/api/cases/'+c['id']+'/compounds.csv')
    assert response.status_code==200
    row=next(csv.DictReader(io.StringIO(response.text)))
    assert row['name']=='Unresolved compound'
    assert row['analysis_status']=='unanalysed'
    assert 'example.org/source' in row['references']
