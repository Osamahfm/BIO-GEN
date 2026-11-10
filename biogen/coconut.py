"""A paginated COCONUT fallback with exact taxon checks and transparent cache provenance."""
import hashlib,json,os,threading,time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from html.parser import HTMLParser
from urllib.parse import quote
import httpx
from .settings import ROOT

FOLDER=ROOT/'data/reference/coconut'
API='https://coconut.naturalproducts.net/api/search'
LOCK=threading.Lock()
LEMON_NAMES={'citrus limon','citrus × limon','citrus x limon','citrus ×limon'}
def normalize(value): return ' '.join(str(value).casefold().split())
def equivalent(value): return 'citrus limon' if normalize(value) in LEMON_NAMES else normalize(value)

class Schemas(HTMLParser):
    def __init__(self):
        super().__init__();self.active=False;self.blocks=[];self.current=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script' and dict(attrs).get('type')=='application/ld+json':
            self.active=True;self.current=[]
    def handle_data(self,data):
        if self.active:self.current.append(data)
    def handle_endtag(self,tag):
        if tag=='script' and self.active:
            self.blocks.append(''.join(self.current));self.active=False

def entities(value):
    if isinstance(value,dict):
        if 'taxonomicRange' in value: yield value
        for v in value.values():yield from entities(v)
    elif isinstance(value,list):
        for v in value:yield from entities(v)

def taxon_match_from_html(text,scientific_name):
    parser=Schemas();parser.feed(text)
    found=[];licenses=[]
    for block in parser.blocks:
        data=json.loads(block)
        if isinstance(data,dict) and data.get('license'): licenses.append(data['license'])
        for entity in entities(data):
            taxa=entity.get('taxonomicRange',[])
            if isinstance(taxa,str):taxa=[taxa]
            for taxon in taxa:
                name=taxon.get('name','') if isinstance(taxon,dict) else taxon
                if equivalent(name)==equivalent(scientific_name):found.append(str(name))
    return sorted(set(found)),licenses

def coverage_for_display(coverage):
    shown=dict(coverage)
    raw=list(coverage.get('technical_warnings',coverage.get('warnings',[])))
    shown['technical_warnings']=raw
    reported=coverage.get('records_reported')
    recovered=coverage.get('unique_candidates_retrieved')
    verified=coverage.get('verified_taxon_records',0)
    if reported is not None and recovered is not None:
        shown['unreconciled_search_hits']=max(0,reported-recovered)
        shown['nonmatching_candidates']=max(0,recovered-verified)
    shown['warnings']=[
        f'Partial source coverage: showing {verified} compounds verified for this plant. The external database returned inconsistent page counts, so additional records may be missing.'
        if 'could not be reconciled' in message else message for message in raw]
    return shown

def get_records(scientific_name,refresh=False):
    query='Citrus limon' if equivalent(scientific_name)=='citrus limon' else scientific_name
    cache=FOLDER/(hashlib.sha256(equivalent(scientific_name).encode()).hexdigest()+'.json')
    if cache.exists() and not refresh:
        result=json.loads(cache.read_text(encoding='utf-8'))
        return result['records'],coverage_for_display(dict(result['coverage'],cache_used=True))
    if os.environ.get('BIOGEN_OFFLINE')=='1':
        return [],{'source':'COCONUT','complete':False,'warnings':['COCONUT has no cached query for this species; online lookup is disabled.']}
    with LOCK:
        if cache.exists() and not refresh:
            result=json.loads(cache.read_text(encoding='utf-8'))
            return result['records'],coverage_for_display(dict(result['coverage'],cache_used=True))
        result=fetch(query,refresh_candidates=refresh)
        # Partial records stay explicitly incomplete; a refresh can retry the source.
        if result['records'] or result['coverage']['complete']:
            FOLDER.mkdir(parents=True,exist_ok=True)
            tmp=cache.with_suffix('.tmp')
            tmp.write_text(json.dumps(result,indent=2),encoding='utf-8')
            tmp.replace(cache)
        return result['records'],coverage_for_display(result['coverage'])

def fetch(query,refresh_candidates=False):
    retrieved=datetime.now(timezone.utc).isoformat()
    coverage={'source':'COCONUT','query':query,'api':API,'retrieved_at':retrieved,'cache_used':False,
              'complete':False,'records_reported':0,'pages_fetched':0,'verified_taxon_records':0,'warnings':[]}
    rows=[];records=[]
    try:
        with httpx.Client(timeout=45,follow_redirects=True,headers={'User-Agent':'BIO-GEN academic research prototype'}) as client:
            seen=set();totals=set();coverage['paging_passes']=[]
            candidate_cache=FOLDER/(hashlib.sha256(equivalent(query).encode()).hexdigest()+'.candidates.json')
            if candidate_cache.exists():
                prior=json.loads(candidate_cache.read_text(encoding='utf-8'))
                rows=prior.get('rows',[]);seen={r['identifier'] for r in rows}
                coverage['records_reported']=prior.get('total',0)
                if coverage['records_reported']:totals.add(coverage['records_reported'])
            # The upstream query has non-unique ordering. Reconcile overlapping pages
            # against the advertised total using different page boundaries.
            sizes=() if candidate_cache.exists() and not refresh_candidates else (100,24,50,75,17,37,61,83)
            for size in sizes:
                if coverage['records_reported'] and len(rows)==coverage['records_reported']:break
                page=1;last_page=1
                while page<=last_page:
                    response=client.post(API,params={'page':page},json={'query':query,'type':'tags','tagType':'organisms','limit':size,'page':page})
                    response.raise_for_status();payload=response.json()['data']
                    last_page=int(payload['last_page']);total=int(payload['total']);totals.add(total)
                    coverage['records_reported']=total;coverage['pages_fetched']+=1
                    for row in payload['data']:
                        identifier=row.get('identifier')
                        if identifier and identifier not in seen:
                            seen.add(identifier);rows.append(row)
                    page+=1
                coverage['paging_passes'].append({'page_size':size,'unique_identifiers':len(rows)})
                if len(totals)==1 and len(rows)==total:break
            coverage['unique_candidates_retrieved']=len(rows)
            FOLDER.mkdir(parents=True,exist_ok=True)
            candidate_cache.write_text(json.dumps({'query':query,'total':coverage['records_reported'],'rows':rows}),encoding='utf-8')
            if len(totals)!=1 or len(rows)!=coverage['records_reported']:
                coverage['warnings'].append('COCONUT page results could not be reconciled with the advertised total; this lookup is explicitly incomplete.')
            def verify(row):
                identifier=row['identifier'];url='https://coconut.naturalproducts.net/compounds/'+quote(identifier,safe='.')
                try:
                    response=client.get(url);response.raise_for_status()
                    matched,licenses=taxon_match_from_html(response.text,query)
                    if not matched:return None,None
                    return {'name':row.get('name') or row.get('iupac_name') or identifier,
                        'scientific_name':query,'plant_part':None,'part_status':'unverified',
                        'smiles':row.get('canonical_smiles') or '',
                        'inchikey':row.get('standard_inchi_key'),'coconut_id':identifier,
                        'source_url':url,'structure_source':url,'source_license':licenses,
                        'source_active':row.get('active'),
                        'evidence_type':'COCONUT species association',
                        'evidence_note':'COCONUT lists this exact species in its compound taxonomic annotations. Plant part and presence in this specimen remain unverified.',
                        'references':[{'source':'COCONUT','source_url':url,'reported_species':matched[0],
                          'plant_part':None,'part_status':'unverified','retrieved_at':retrieved,
                          'note':'Compound-level database association; individual literature citations are not asserted as species-specific proof.'}]},None
                except Exception as exc:
                    return None,'Could not verify '+identifier+': '+str(exc)
                finally:time.sleep(.15)
            with ThreadPoolExecutor(max_workers=3) as workers:
                for record,error in workers.map(verify,rows):
                    if record:records.append(record)
                    if error:coverage['warnings'].append(error)
            coverage['verified_taxon_records']=len(records)
            coverage['complete']=not coverage['warnings']
    except Exception as exc:
        coverage['warnings'].append('COCONUT lookup unavailable: '+str(exc))
    return {'records':records,'coverage':coverage}
