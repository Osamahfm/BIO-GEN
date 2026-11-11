import csv
import html
import io
import json
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from . import chemistry, part_profiles, production, profiling, quality, store
from .settings import DATA, ROOT

app = FastAPI(title='BIO-GEN', description='Processes 1–4 research proof of concept', version='0.1.0')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
(DATA / 'images').mkdir(exist_ok=True)


@app.exception_handler(KeyError)
async def missing(_, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({'detail': str(exc)}, status_code=404)


@app.exception_handler(ValueError)
async def invalid(_, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({'detail': str(exc)}, status_code=409)


class Revision(BaseModel):
    revision: int = Field(ge=0)


class RenameCase(Revision):
    title: str = Field(min_length=1, max_length=180)


class Identify(Revision):
    plant_part: str | None = Field(default=None, max_length=60)


class Profile(Revision):
    scientific_name: str = Field(min_length=3, max_length=160)
    plant_part: str = Field(min_length=2, max_length=60)
    target_disease: str = Field(min_length=2, max_length=250)
    collection_notes: str = Field(default='', max_length=4000)
    identity_basis: str = Field(default='', max_length=500)
    researcher: str = Field(min_length=2, max_length=160)
    source_url: str = Field(default='', max_length=2000)


class Filters(Revision):
    refresh_external: bool = False
    apply_property_filters: bool = False
    include_part_unverified: bool = True
    max_mw: float = Field(default=750, ge=50, le=3000)
    max_logp: float = Field(default=7, ge=-10, le=20)
    min_qed: float = Field(default=0, ge=0, le=1)


class Review(Revision):
    reviewer: str = Field(min_length=2, max_length=160)
    role: str = Field(min_length=2, max_length=100)
    outcome: str = Field(pattern='^(evidence_supported|explicit_assumption|unresolved)$')
    note: str = Field(min_length=10, max_length=5000)
    source_url: str = Field(default='', max_length=2000)


@app.get('/', response_class=HTMLResponse)
def index():
    return (ROOT / 'static/index.html').read_text(encoding='utf-8')


@app.get('/api/status')
def status():
    import importlib.metadata as md
    return {'application': 'BIO-GEN', 'model': profiling.model_status(), 'plants': len(profiling.knowledge().plants),
            'components': {x: md.version(x) for x in ['plantcv', 'rdkit', 'fastapi']},
            'scope': 'Processes 1–4', 'case_count': len(store.list_cases()), 'compound_database': __import__('biogen.plant_compounds', fromlist=['status']).status()}


@app.get('/api/plants')
def plants(q: str = ''):
    return profiling.plants(q[:500])


@app.get('/api/plant-options')
def plant_options():
    from .plant_catalog import options
    return options()


@app.get('/api/plant-part-references')
def plant_part_references(scientific_name: str = '', plant_part: str = 'leaves', target_disease: str = ''):
    from .plant_catalog import profile_identity
    identity = profile_identity(scientific_name[:160])
    return part_profiles.references(identity['scientific_name'], plant_part[:60], target_disease[:250])


@app.get('/api/cases')
def cases():
    return [{'id': c['id'], 'revision': c['revision'], 'stage': c['stage'], 'profile': c['profile'],
             'updated_at': c['updated_at']} for c in store.list_cases()]


@app.post('/api/cases')
def create_case(title: str = Form('New research case')):
    return store.create({'title': title[:180]})


@app.get('/api/cases/{case_id}')
def get_case(case_id: str):
    return store.get(case_id)


@app.patch('/api/cases/{case_id}')
def rename_case(case_id: str, body: RenameCase):
    title = body.title.strip()
    if not title:
        raise HTTPException(422, 'Enter a case title.')
    case = store.get(case_id)
    profile = dict(case['profile'], title=title)
    return store.update(case_id, body.revision, {'profile': profile}, 'Case renamed')


@app.delete('/api/cases/{case_id}')
def delete_case(case_id: str, revision: int):
    filenames = store.delete(case_id, revision)
    cleanup_pending = False
    for filename in filenames:
        if not re.fullmatch(r'[a-f0-9]{32}(?:-overlay)?\.(?:jpg|png)', filename):
            continue
        try:
            (DATA / 'images' / filename).unlink(missing_ok=True)
        except OSError:
            cleanup_pending = True
    return {'deleted': case_id, 'image_cleanup_pending': cleanup_pending}


@app.get('/api/cases/{case_id}/history')
def history(case_id: str):
    store.get(case_id)
    return store.history(case_id)


@app.post('/api/cases/{case_id}/image')
async def upload(case_id: str, revision: int = Form(...), file: UploadFile = File(...)):
    store.get(case_id)
    content = await file.read(12 * 1024 * 1024 + 1)
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(413, 'Maximum image size is 12 MB.')
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > 25_000_000:
                raise HTTPException(413, 'Image exceeds 25 megapixels.')
            image = ImageOps.exif_transpose(image).convert('RGB')
            image.load()
            name = uuid.uuid4().hex + '.jpg'
            image.save(DATA / 'images' / name, quality=92)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, 'Please upload a readable JPG, PNG, or WebP image.')
    old = store.get(case_id)
    profile = dict(old['profile'], image=name)
    # Identity confirmation refers to the specimen/image: replacing it requires reconfirmation.
    profile.pop('confirmed', None)
    return store.update(case_id, revision, {'profile': profile, 'stage': 'C0', 'prediction': None,
                        'quality': None, 'discovery': None, 'production': None}, 'Specimen image uploaded; downstream results reset')


@app.get('/api/images/{filename}')
def image(filename: str):
    if not re.fullmatch(r'[a-f0-9]{32}(?:-overlay)?\.(?:jpg|png)', filename):
        raise HTTPException(404)
    path = DATA / 'images' / filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


@app.post('/api/cases/{case_id}/identify')
def identify(case_id: str, body: Identify):
    case = store.get(case_id)
    selected_part = body.plant_part if body.plant_part is not None else case['profile'].get('plant_part', '')
    if not selected_part.strip():
        return dict(case, identity_guidance={
            'mode': 'select_part',
            'message': 'Choose the plant part shown in the image before requesting a suggestion.',
        })
    if part_profiles.normalize_part(selected_part) != 'leaves':
        return dict(case, identity_guidance={
            'mode': 'reference_review',
            'plant_part': part_profiles.normalize_part(selected_part),
            'message': 'Use the plant-part references to review the species, then save the profile.',
        })
    if not case['profile'].get('image'):
        raise HTTPException(422, 'Upload a leaf image first.')
    path = DATA / 'images' / case['profile']['image']
    if not profiling.has_green_tissue(path):
        if case.get('prediction'):
            case = store.update(case_id, body.revision, {'prediction': None}, 'Leaf suggestions withheld after image screening')
        return dict(case, identity_guidance={
            'mode': 'reference_review',
            'plant_part': 'leaves',
            'message': 'Too little green tissue for a leaf suggestion. Check the plant part and confirm the identity using a reference.',
        })
    result = dict(profiling.identify(path), plant_part='leaves')
    return store.update(case_id, body.revision, {'prediction': result}, 'Ayur-Ai image prediction recorded')


@app.post('/api/cases/{case_id}/profile')
def confirm(case_id: str, body: Profile):
    case = store.get(case_id)
    data = body.model_dump(exclude={'revision'}, exclude_unset=True)
    data = {k: v.strip() for k, v in data.items()}
    if not all(data[x] for x in ['scientific_name', 'plant_part', 'target_disease', 'researcher']):
        raise HTTPException(422, 'Complete the species, plant part, target disease, and researcher fields.')
    from .plant_catalog import profile_identity
    data.update(profile_identity(data['scientific_name']))
    data['plant_part'] = part_profiles.normalize_part(data['plant_part'])
    refs = part_profiles.references(data['scientific_name'], data['plant_part'], data['target_disease'])
    profile = dict(case['profile'], **data, confirmed=True, confirmed_at=store.now(),
                   part_references={key: refs[key] for key in ('images', 'studies')})
    changes = {'profile': profile, 'stage': 'C1', 'quality': None, 'discovery': None, 'production': None}
    if data['plant_part'] != 'leaves':
        changes['prediction'] = None
    return store.update(case_id, body.revision, changes,
                        ('Plant profile saved; exact species unconfirmed' if not data['species_confirmed'] else 'Plant identity and disease context confirmed; downstream results reset'))


@app.post('/api/cases/{case_id}/quality')
def assess(case_id: str, body: Revision):
    case = store.get(case_id)
    if not case['profile'].get('confirmed') or not case['profile'].get('image'):
        raise HTTPException(422, 'Confirm Process 1 and upload an image before running Process 2.')
    overlay = uuid.uuid4().hex + '-overlay.png'
    result = quality.analyse(DATA / 'images' / case['profile']['image'], DATA / 'images' / overlay,
                             case['profile'].get('plant_part', 'leaves'))
    return store.update(case_id, body.revision, {'quality': result, 'discovery': None, 'production': None, 'stage': 'C2'}, 'Specimen photo quality analysis completed')


@app.post('/api/cases/{case_id}/discovery')
def discover(case_id: str, body: Filters):
    case = store.get(case_id)
    if not case.get('quality') or not case['profile'].get('confirmed'):
        raise HTTPException(422, 'Complete Processes 1 and 2 before candidate discovery.')
    if case['profile'].get('species_confirmed') is False or not case['profile'].get('scientific_name'):
        raise HTTPException(422, 'This case is saved with a training label only. Image-quality testing is available; confirm an exact scientific species in Process 1 before compound discovery.')
    if not quality.current_for_part(case['quality'], case['profile'].get('plant_part')):
        raise HTTPException(422, 'Rerun Process 2 with the checks for this plant part before continuing.')
    result = chemistry.discover(case['profile']['scientific_name'], case['profile']['plant_part'],
                                **body.model_dump(exclude={'revision'}))
    result['recommendations_held'] = any(f['critical'] for f in case['quality']['flags'])
    return store.update(case_id, body.revision, {'discovery': result, 'production': None, 'stage': 'C3'}, 'Phytochemical evidence retrieved and molecular descriptors calculated')


@app.get('/api/cases/{case_id}/production')
def production_options(case_id: str):
    return production.options(store.get(case_id))


@app.post('/api/cases/{case_id}/production')
def simulate_production(case_id: str, body: Revision):
    case = store.get(case_id)
    if case['revision'] != body.revision:
        raise HTTPException(409, 'This case changed in another window. Reload before saving.')
    configuration = production.options(case)
    if not configuration['available']:
        raise HTTPException(422, configuration['reason'])
    try:
        result = production.simulate(case, configuration)
    except (ImportError, RuntimeError) as exc:
        raise HTTPException(503, 'The production solver could not complete the simulation.') from exc
    return store.update(case_id, body.revision, {'production': result, 'stage': 'C4'},
                        'EGS1 production scenarios simulated and saved')


@app.post('/api/cases/{case_id}/reviews')
def review(case_id: str, body: Review):
    case = store.get(case_id)
    if body.outcome == 'evidence_supported' and not body.source_url.startswith(('https://', 'http://')):
        raise HTTPException(422, 'Evidence-supported reviews require a source URL.')
    entry = dict(body.model_dump(exclude={'revision'}), at=store.now(), stage=case['stage'])
    # A note is not a validated resolution of a technical image-quality failure.
    return store.update(case_id, body.revision, {'reviews': case['reviews'] + [entry]}, 'Review recorded; measured flags retained')


@app.get('/api/cases/{case_id}/export.json')
def export_json(case_id: str):
    case = store.get(case_id)
    return Response(json.dumps({'case': case, 'history': store.history(case_id)}, indent=2, ensure_ascii=False),
                    media_type='application/json', headers={'Content-Disposition': f'attachment; filename="BIO-GEN-{case_id[:8]}.json"'})


@app.get('/api/cases/{case_id}/compounds.csv')
def export_csv(case_id: str):
    case = store.get(case_id)
    out = io.StringIO(newline='')
    fields = ['name', 'scientific_name', 'plant_part', 'smiles', 'source_url', 'structure_source',
              'mw', 'logp', 'tpsa', 'qed', 'selected', 'evidence_status', 'recommendations_held', 'part_status', 'references', 'analysis_status', 'reason', 'property_filters_applied', 'retrieval_complete']
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    discovery = case.get('discovery') or {}
    for r in discovery.get('compounds', []) + discovery.get('invalid', []):
        flat = dict(r, **r.get('descriptors', {}), retrieval_complete=discovery.get('coverage', {}).get('retrieval_complete_for_query', False), analysis_status='calculated' if r.get('descriptors') else 'unanalysed', property_filters_applied=discovery.get('filters', {}).get('applied', True), references=json.dumps(r.get('references', []), ensure_ascii=False), evidence_status='literature_reported_not_measured_in_specimen',
                    recommendations_held=case['discovery']['recommendations_held'])
        writer.writerow({k: ('\'' + str(flat.get(k, '')) if str(flat.get(k, '')).startswith(('=', '+', '-', '@')) else flat.get(k, '')) for k in fields})
    return Response(out.getvalue(), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="BIO-GEN-{case_id[:8]}-compounds.csv"'})


@app.get('/api/cases/{case_id}/report', response_class=HTMLResponse)
def report(case_id: str):
    c = store.get(case_id)
    e = lambda value: html.escape(str(value if value is not None else 'Not supplied'))
    def source(url):
        return f'<a href="{e(url)}">{e(url)}</a>' if str(url).startswith(('https://', 'http://')) else 'No reference supplied'
    p, q, d = dict(c['profile']), c.get('quality'), c.get('discovery')
    if p.get('species_confirmed') is False: p['scientific_name'] = 'Unconfirmed — training label only'
    facts = ''.join(f'<tr><th>{e(label)}</th><td>{e(p.get(key))}</td></tr>' for label, key in [
        ('Scientific name', 'scientific_name'), ('Plant label', 'plant_label'), ('Identity resolution', 'identity_resolution'), ('Plant part', 'plant_part'), ('Target human disease / indication', 'target_disease'),
        ('Researcher', 'researcher'), ('Identity basis', 'identity_basis'), ('Collection notes', 'collection_notes')] if key != 'identity_basis' or p.get(key))
    parts = [f'<h2>01 · Plant & disease profiling</h2><table>{facts}</table>']
    if p.get('source_url'):
        parts.append(f'<p>Identity reference: {source(p["source_url"])}</p>')
    refs = p.get('part_references') or {}
    for heading, records in [('Image references', refs.get('images', [])),
                             ('Part-specific research', refs.get('studies', []))]:
        if records:
            parts.append(f'<h3>{heading}</h3>')
            for ref in records:
                context = ' · '.join(ref[key] for key in ('kind', 'indication', 'note') if ref.get(key))
                parts.append(f'<p><strong>{e(ref["label"])}</strong> {e(context)}<br>{source(ref["url"])}</p>')
    if q and not quality.current_for_part(q, p.get('plant_part')):
        parts.append('<h2>02 · Visual quality</h2><p>Rerun Process 2 to assess this plant part.</p>')
        q, d = None, None
    if q:
        parts.append('<h2>02 · Plant health & visual quality</h2><p>' + e(q['method']) + '</p>')
        parts.append('<table>' + ''.join(f'<tr><th>{e(k.replace("_", " "))}</th><td>{e(v)}</td></tr>' for k,v in q['metrics'].items() if k != 'plantcv_observation_fields') + '</table>')
        parts.extend('<p class="notice">' + e(f['message']) + '</p>' for f in q['flags'])
        parts.append('<ul>' + ''.join('<li>'+e(x)+'</li>' for x in q['limitations']) + '</ul>')
    if d:
        parts.append('<h2>03 · Phytochemicals & candidate triage</h2>')
        if d.get('coverage'):
            parts.append('<p>Database: '+e(d['coverage']['database'].get('release'))+' · '+e(len(d['compounds']))+' valid unique structures · '+e(d.get('part_supported_structures',0))+' with selected-part support. All retrieved records are retained; database coverage does not establish chemical completeness.</p>')
        if d.get('coverage', {}).get('fallback'):
            external=d['coverage']['fallback']
            parts.append('<p class="notice">Additional source: COCONUT. Source coverage: '+('complete for the provider query' if external.get('complete') else 'incomplete; available verified results only')+'. Retrieved '+e(external.get('retrieved_at'))+'.</p>')
        if d['recommendations_held']:
            parts.append('<p class="notice">Recommendations held: critical image-quality issues remain.</p>')
        parts.append('<p>'+('Optional property filters applied. ' if d['filters'].get('applied',True) else 'Property filters disabled; all retrieved structures shown. ')+'Settings: MW ≤ ' + e(d['filters'].get('max_mw')) + '; LogP ≤ ' + e(d['filters'].get('max_logp')) + '; QED ≥ ' + e(d['filters'].get('min_qed')) + '.</p>')
        parts.append('<table><tr><th>Compound</th><th>MW</th><th>LogP</th><th>TPSA</th><th>QED</th><th>Meets filters</th></tr>')
        for r in d['compounds']:
            m=r['descriptors']
            parts.append('<tr>'+''.join('<td>'+e(v)+'</td>' for v in [r['name'],m['mw'],m['logp'],m['tpsa'],m['qed'],'Yes' if r['selected'] else 'No'])+'</tr>')
        parts.append('</table>')
        for r in d['compounds']:
            parts.append('<h3>'+e(r['name'])+'</h3><p>'+e(r.get('evidence_note'))+'</p><p>Association: '+source(r.get('source_url'))+'<br>Structure: '+source(r.get('structure_source'))+'</p>')
        parts.extend('<p class="notice">'+e(x)+'</p>' for x in d['evidence_gaps'])
        for record in d.get('invalid', []):
            parts.append('<p>Unanalysed source record: '+e(record.get('name'))+' · '+e(record.get('reason'))+' · '+source(record.get('source_url'))+'</p>')
    if simulation := c.get('production'):
        parts.append('<h2>04 · Genetic & production simulation</h2>')
        parts.append(f'<p>{e(simulation["model_id"])} · input revision {e(simulation["input_revision"])} · '
                     f'{e(simulation["method"])} with {e(simulation["engine"])} {e(simulation["engine_version"])}. '
                     f'Objective: {e(simulation["objective"])}. Values in {e(simulation["unit"])}.</p>')
        parts.append('<table><tr><th>Scenario</th><th>Nominal flux</th><th>Low supply</th><th>High supply</th></tr>')
        for row in simulation['scenarios']:
            parts.append('<tr>' + ''.join(f'<td>{e(row[key])}</td>' for key in
                         ('name', 'flux', 'low_supply_flux', 'high_supply_flux')) + '</tr>')
        parts.append('</table>')
        parts.extend(f'<p>{e(text)}</p>' for text in simulation['limitations'])
        parts.extend(f'<p>{e(ref["label"])} · {source(ref["url"])}</p>' for ref in simulation['sources'])
    parts.append('<h2>Review records</h2>')
    for r in c['reviews']:
        parts.append('<p><b>'+e(r['reviewer'])+' · '+e(r['role'])+'</b> · '+e(r['outcome'])+'<br>'+e(r['note'])+'<br>'+source(r.get('source_url'))+'</p>')
    if not c['reviews']:
        parts.append('<p>No review has been recorded. No expert validation is implied.</p>')
    parts.append('<h2>Case history</h2><ol>'+''.join('<li>'+e(ev['action'])+' · '+e(ev['at'])+'</li>' for ev in c['events'])+'</ol>')
    parts.insert(0, f'<p><a href="/api/cases/{c["id"]}/export.json">Download full case and history (JSON)</a> · <a href="/api/cases/{c["id"]}/compounds.csv">Download compound results (CSV)</a></p>')
    return '<!doctype html><html><head><meta charset="utf-8"><title>BIO-GEN research report</title><style>body{font:14px system-ui;max-width:950px;margin:45px auto;padding:0 20px;color:#143f36;line-height:1.6}h1{font:38px Georgia}h2{margin-top:35px;border-bottom:1px solid #dde7da;padding-bottom:10px}h3{margin-bottom:5px}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #e4eadf;text-align:left}th{color:#587351;background:#f5f8f1}a{color:#347252;overflow-wrap:anywhere;font-size:12px}.notice{padding:13px;background:#fcf6e8}button{padding:10px}@media print{button{display:none}body{margin:15px;max-width:none}tr{break-inside:avoid}h2{break-after:avoid}}</style></head><body><button onclick="print()">Print / save as PDF</button><h1>BIO-GEN research case</h1><p>'+e(p.get('title'))+' · '+e(c['stage'])+' · revision '+e(c['revision'])+'<br>Case '+e(c['id'])+'</p><p class="notice">Processes 1–4 research proof of concept. Literature-reported compounds are not confirmed in this specimen. Visual measurements do not establish disease, purity, efficacy, or safety.</p>'+''.join(parts)+'</body></html>'
