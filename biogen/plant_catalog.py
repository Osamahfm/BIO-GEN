"""Shared UI/model label inventory. Missing or ambiguous class names never disappear."""
import json,re
from .settings import AYUR,MODELS,ROOT

def normalize(value):return re.sub(r'[^a-z0-9]+',' ',str(value).casefold()).strip()
def trained_labels():
    p=MODELS/'identification.json'
    return json.loads(p.read_text(encoding='utf-8')).get('classes',[]) if p.exists() else []

def options():
    base=json.loads((AYUR/'data/knowledge_base/plants.json').read_text(encoding='utf-8'))['plants']
    configured=json.loads((ROOT/'data/reference/training-labels.json').read_text(encoding='utf-8'))['suggested_mappings']
    entries={p['botanical_name']:dict(p,training_labels=[],reference_profile=True,requires_scientific_confirmation=('spp.' in p['botanical_name'])) for p in base}
    for label in trained_labels():
        target=configured.get(label)
        match=None
        if target:
            scientific,common=target
            match=entries.get(scientific)
            if match is None:
                match={'id':normalize(scientific).replace(' ','_'),'botanical_name':scientific,'common_names':[common],
                       'training_labels':[],'reference_profile':False,'requires_scientific_confirmation':False}
                entries[scientific]=match
        else:
            # Only an unambiguous, exact known alias is reused. No fuzzy taxonomy.
            matches=[p for p in entries.values() if normalize(label) in {normalize(x) for x in p.get('common_names',[])+p.get('folder_aliases',[])}]
            if len(matches)==1:match=matches[0]
        if match is None:
            common=label.replace('_',' ')
            match={'id':'training_'+label,'botanical_name':'','common_names':[common],'training_labels':[],
                   'reference_profile':False,'requires_scientific_confirmation':True}
            entries['training:'+label]=match
        match['training_labels'].append(label)
    result=[]
    for entry in entries.values():
        name=entry['botanical_name'];common=entry['common_names'][0]
        entry['display_name']=name+' ('+common+')' if name else common+' (scientific species needs confirmation)'
        if name and entry['requires_scientific_confirmation']:
            entry['display_name']=name+' ('+common+' — confirm exact species)'
        entry['trained']=bool(entry['training_labels'])
        result.append(entry)
    return sorted(result,key=lambda p:p['display_name'].casefold())

def resolve(value):
    text=str(value).strip();key=normalize(text)
    matches=[p for p in options() if key in {normalize(x) for x in [p['botanical_name'],p['display_name']]+p['common_names']+p['training_labels'] if x}]
    if len(matches)==1:
        plant=matches[0]
        if plant['requires_scientific_confirmation']:
            raise ValueError('This training label does not identify one exact species. Enter a confirmed scientific species name before continuing.')
        return plant['botanical_name']
    return text

def label_info(label):
    return next((p for p in options() if label in p['training_labels']),None)


def profile_identity(value):
    """Allow label-only research cases without treating a class name as a species."""
    text=str(value).strip();key=normalize(text)
    matches=[p for p in options() if key in {normalize(x) for x in [p['botanical_name'],p['display_name']]+p['common_names']+p['training_labels'] if x}]
    plant=matches[0] if len(matches)==1 else None
    broad=(plant and plant['requires_scientific_confirmation']) or (not plant and (len(text.split())<2 or re.search(r"\b(spp|sp)\.?$",text,re.I)))
    if broad:
        label=plant['training_labels'][0] if plant and plant['training_labels'] else (plant['common_names'][0] if plant else text)
        return {'scientific_name':'','plant_label':label,'display_label':plant['display_name'] if plant else text,
                'identity_resolution':'training_label_only','species_confirmed':False}
    scientific=plant['botanical_name'] if plant else text
    return {'scientific_name':scientific,'plant_label':plant['training_labels'][0] if plant and plant['training_labels'] else scientific,
            'display_label':plant['display_name'] if plant else scientific,'identity_resolution':'researcher_supplied_species','species_confirmed':True}
