import json
from biogen import coconut

def html(taxon):
    return '<script type="application/ld+json">'+json.dumps({'license':'https://creativecommons.org/licenses/by/4.0/','about':{'taxonomicRange':[taxon]}})+'</script>'

def test_exact_species_check_rejects_prefix_matches_and_accepts_hybrid_spelling():
    assert coconut.taxon_match_from_html(html('Citrus limonia'),'Citrus limon')[0]==[]
    assert coconut.taxon_match_from_html(html('Citrus × limon'),'Citrus limon')[0]==['Citrus × limon']

def test_overlapping_pages_are_reconciled_and_neighboring_species_excluded(monkeypatch,tmp_path):
    monkeypatch.setattr(coconut,'FOLDER',tmp_path)
    rows={name:{'identifier':name,'canonical_smiles':'CCO','name':name,'active':True} for name in ['CNP-A','CNP-B','CNP-C']}
    class Response:
        def __init__(self,data=None,text=''):self.data=data;self.text=text
        def raise_for_status(self):pass
        def json(self):return self.data
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,params,json):
            if json['limit']==100:
                names=['CNP-A','CNP-B'] if json['page']==1 else ['CNP-A']
                last=2
            else:
                names=['CNP-A','CNP-B','CNP-C'];last=1
            return Response({'data':{'last_page':last,'total':3,'data':[rows[n] for n in names]}})
        def get(self,url):
            return Response(text=html('Citrus limonia' if url.endswith('CNP-C') else 'Citrus limon'))
    monkeypatch.setattr(coconut.httpx,'Client',Client)
    monkeypatch.setattr(coconut.time,'sleep',lambda _:None)
    result=coconut.fetch('Citrus limon')
    assert result['coverage']['complete']
    assert result['coverage']['unique_candidates_retrieved']==3
    assert len(result['coverage']['paging_passes'])==2
    assert len(result['records'])==2
    assert all(r['part_status']=='unverified' for r in result['records'])

def test_network_failure_is_not_reported_as_complete_absence(monkeypatch):
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):raise coconut.httpx.ConnectError('Offline')
        def __exit__(self,*args):pass
    monkeypatch.setattr(coconut.httpx,'Client',Client)
    result=coconut.fetch('Citrus limon')
    assert not result['coverage']['complete']
    assert result['coverage']['warnings']
    assert result['records']==[]


def test_coverage_warning_is_clear_and_preserves_original_diagnostics():
    old={'complete':False,'records_reported':293,'unique_candidates_retrieved':285,'verified_taxon_records':258,'warnings':['COCONUT page results could not be reconciled with the advertised total; this lookup is explicitly incomplete.']}
    result=coconut.coverage_for_display(old)
    assert result['unreconciled_search_hits']==8
    assert result['nonmatching_candidates']==27
    assert 'showing 258' in result['warnings'][0]
    assert result['technical_warnings']==old['warnings']
    assert not result['complete']
