const $=id=>document.getElementById(id);
let current=null, step=1, system=null, plantCatalog=[];
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeURL=u=>/^https?:\/\//i.test(u||'')?u:'#';
function plantOption(value){const text=String(value||'').trim().toLowerCase();if(!text)return null;const matches=plantCatalog.filter(p=>[p.botanical_name,p.display_name,...p.common_names,...(p.training_labels||[])].filter(Boolean).some(x=>x.toLowerCase()===text));return matches.length===1?matches[0]:null;}
function plantDisplayName(name){if(!name)return '';const plant=plantOption(name);return plant?.display_name||name;}
function plantScientificName(value){const text=String(value||'').trim();const plant=plantOption(text);if(plant?.requires_scientific_confirmation)return plant.display_name;return plant?.botanical_name||text;}
function toast(message,error=false){$('toast').textContent=message;$('toast').className=error?'error':'';$('toast').style.display='block';clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>$('toast').style.display='none',6500)}
async function api(url,options={}){const r=await fetch(url,options);if(!r.ok){const d=await r.json().catch(()=>({detail:r.statusText}));throw Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail))}return r.json()}
async function busy(fn){document.body.classList.add('busy');try{await fn()}catch(e){toast(e.message,true)}finally{document.body.classList.remove('busy')}}
async function mutate(action,data){current=await api(`/api/cases/${current.id}/${action}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:current.revision,...data})});render();await refreshCases()}
function imageURL(name){return `/api/images/${encodeURIComponent(name)}`}
function date(x){return new Date(x).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})}
async function refreshCases() {
 const cases = await api('/api/cases');
 const list = $('caseList');
 $('caseCount').textContent = cases.length;
 list.innerHTML = cases.map(c => {
   const title = c.profile.title || c.profile.scientific_name || 'Research case';
   return `<div class="case-list-row"><button type="button" class="case-item ${c.id === current?.id ? 'active' : ''}" data-case="${esc(c.id)}"><b>${esc(title)}</b><small>${esc(c.stage)} · revision ${c.revision} · ${date(c.updated_at)}</small></button><div class="case-actions"><button type="button" class="case-action" data-rename-case="${esc(c.id)}" aria-label="Rename ${esc(title)}">Rename</button><button type="button" class="case-action case-delete" data-delete-case="${esc(c.id)}" aria-label="Delete ${esc(title)}">Delete</button></div></div>`;
 }).join('');
 list.querySelectorAll('[data-case]').forEach(button => {
   button.onclick = () => busy(async () => {
     current = await api('/api/cases/' + button.dataset.case);
     step = Math.min(4, Number(current.stage.slice(1)) || 1);
     render();
     await refreshCases();
   });
 });
 list.querySelectorAll('[data-rename-case]').forEach(button => {
   button.onclick = () => openRenameDialog(cases.find(c => c.id === button.dataset.renameCase));
 });
 list.querySelectorAll('[data-delete-case]').forEach(button => {
   button.onclick = () => {
     const target = cases.find(c => c.id === button.dataset.deleteCase);
     const dialog = $('deleteCaseDialog');
     $('deleteCaseName').textContent = target.profile.title || target.profile.scientific_name || 'Research case';
     $('deleteCaseForm').onsubmit = event => {
       event.preventDefault();
       dialog.close();
       busy(async () => {
         const result = await api(`/api/cases/${encodeURIComponent(target.id)}?revision=${target.revision}`, {method:'DELETE'});
         if (current?.id === target.id) {
           current = null;
           step = 1;
           render();
         }
         await refreshCases();
         toast(result.image_cleanup_pending ? 'Case deleted. Some image files could not be removed.' : 'Case deleted.');
       });
     };
     dialog.showModal();
   };
 });
}
function openRenameDialog(target) {
 const dialog = $('renameCaseDialog');
 const form = $('renameCaseForm');
 const input = $('renameCaseInput');
 const error = $('renameCaseError');
 const submit = $('saveCaseName');
 const cancel = $('cancelCaseRename');
 input.value = target.profile.title || target.profile.scientific_name || '';
 error.textContent = '';
 form.onsubmit = async event => {
   event.preventDefault();
   const title = input.value.trim();
   if (!title) {
     error.textContent = 'Enter a case title.';
     input.focus();
     return;
   }
   error.textContent = '';
   submit.disabled = cancel.disabled = true;
   try {
     const renamed = await api(`/api/cases/${encodeURIComponent(target.id)}`, {
       method: 'PATCH', headers: {'Content-Type':'application/json'},
       body: JSON.stringify({title, revision:target.revision}),
     });
     if (current?.id === target.id) {
       current = renamed;
       renderCaseHeader();
       summary();
     }
     dialog.close();
     await refreshCases();
     toast('Case renamed.');
   } catch (failure) {
     if (dialog.open) error.textContent = failure.message;
     else toast(failure.message, true);
   } finally {
     submit.disabled = cancel.disabled = false;
   }
 };
 dialog.oncancel = event => { if (submit.disabled) event.preventDefault(); };
 dialog.showModal();
 input.select();
}

async function newCase(title){const data=new FormData();data.set('title',title);current=await api('/api/cases',{method:'POST',body:data});step=1;render();await refreshCases()}
function bind(id,fn){const e=$(id);if(e)e.onclick=()=>busy(fn)}
function summary(){if(!current){$('caseSummary').innerHTML='<p class="subtle">Every result belongs to a saved research case. Create one to connect your inputs, evidence and decisions.</p>';$('uncertainty').innerHTML='<p class="subtle">Missing data and unresolved questions will appear here.</p>';$('timeline').innerHTML='<p class="subtle">Your research trail starts with C0.</p>';return}
 const p=current.profile;$('caseSummary').innerHTML=[['Case',current.id.slice(0,8).toUpperCase()],['Stage',current.stage],['Plant',p.display_label||plantDisplayName(p.scientific_name)||p.plant_label||'Not supplied'],['Species',p.species_confirmed===false?'Unconfirmed':plantDisplayName(p.scientific_name)||'Not confirmed'],['Plant part',p.plant_part||'Not supplied'],['Target disease',p.target_disease||'Not supplied'],['Researcher',p.researcher||'Not supplied']].map(([a,b])=>`<div class="summary-row"><span>${a}</span><b>${esc(b)}</b></div>`).join('');
 let flags=[];if(p.species_confirmed===false)flags.push('Training label saved. Exact species remains unconfirmed; image-quality testing is available and compound discovery is held.');if(!p.confirmed)flags.push('Plant identity needs researcher confirmation.');if(current.prediction?.plant_part==='leaves')flags.push('Verify tentative leaf matches against the specimen or a reliable source.');if(needsPartQualityUpdate(current.quality,p.plant_part))flags.push('Rerun Process 2 for the selected plant part.');else if(current.quality)flags.push(...current.quality.flags.map(f=>f.message));if(current.discovery){flags.push('Compounds are literature reported, not measured in this specimen.');flags.push(...current.discovery.evidence_gaps)}if(current.production)flags.push('Production scenarios use assumed pathway capacities. Experimental validation is needed before recommendations.');
 $('uncertainty').innerHTML=flags.map(f=>`<div class="flag">${esc(f)}</div>`).join('')+(current.reviews||[]).slice(-3).map(r=>`<div class="review-note"><b>${esc(r.reviewer)} · ${esc(r.role)}</b><span class="pill amber">${esc(r.outcome.replaceAll('_',' '))}</span><p>${esc(r.note)}</p>${r.source_url?`<a href="${esc(safeURL(r.source_url))}" target="_blank" rel="noopener">Review evidence ↗</a>`:''}</div>`).join('');
 $('timeline').innerHTML=[...current.events].reverse().slice(0,7).map(e=>`<div class="timeline-item">${esc(e.action)}<small>${date(e.at)}${e.revision!=null?' · revision '+e.revision:''}</small></div>`).join('');}
function renderCaseHeader(){const p=current?.profile||{};$('caseCrumb').textContent=p.title||'Overview';$('revisionStat').textContent=current?.stage||'C0';$('revisionLabel').textContent=current?'Revision '+current.revision+' · saved locally':'Versioned case record';$('savedStatus').textContent=current?'Saved '+date(current.updated_at):'Create a case to begin';$('exportButton').disabled=!current;$('reviewButton').disabled=!current;}
function render(){const p=current?.profile||{};renderCaseHeader();
 document.querySelectorAll('[data-step]').forEach(b=>b.classList.toggle('active',+b.dataset.step===step));[1,2,3,4].forEach(i=>$('step'+i+'State').classList.toggle('done',i===1?!!p.confirmed:i===2?!!current?.quality:i===3?!!current?.discovery:!!current?.production));summary();
 if(!current){$('processPanel').innerHTML=`<div class="empty"><span class="empty-symbol">✳</span><div class="eyebrow">TURN AN IDEA INTO A RESEARCH CASE</div><h2>Give your discovery a starting point.</h2><p>Create a case, add a medicinal plant and follow the evidence through identity, visual quality and chemical exploration.</p><button class="button primary" id="welcomeNew">＋ Create your first case</button><p><button class="button outline" id="exampleCase">Explore a sourced Tulsi example →</button></p></div>`;bind('welcomeNew',async()=>$('newDialog').showModal());bind('exampleCase',example);return}
 if(step===1)renderProfile();else if(step===2)renderQuality();else if(step===3)renderDiscovery();else renderProduction();}
function renderProfile(){const p=current.profile;$('processPanel').innerHTML=`<div class="section-top"><div><div class="panel-kicker">PROCESS 01 · C0 → C1</div><h3>Build the plant–disease case</h3><p class="subtle">The target human disease is research context. Plant identity requires confirmation.</p></div><span class="pill">${p.confirmed?(p.species_confirmed===false?'LABEL SAVED':'CONFIRMED'):'DRAFT'}</span></div>
 ${p.image?`<div class="specimen"><img src="${imageURL(p.image)}" alt="Uploaded specimen"><div><b>Specimen image attached</b><p class="subtle">Replacing the image resets identity confirmation and later results.</p><button type="button" class="button outline" id="predictButton">Review plant identity →</button></div></div>`:''}
 <div class="upload-box"><span>↥</span><label>${p.image?'Replace specimen image':'Add a specimen image'}<input type="file" id="imageInput" accept="image/jpeg,image/png,image/webp"></label></div>
 ${!system?.model?.ready?'<div class="notice">The image classifier is not available yet. You can record a researcher-confirmed species while it is being prepared.</div>':''}
 ${current.prediction?.plant_part==='leaves'?`<div class="predictions" id="profilePredictions"><b class="subtle">Tentative matches from the model’s training labels</b>${current.prediction.predictions.map((r,i)=>`<div class="prediction-row"><button type="button" data-prediction="${i}">${esc(r.display_name || plantDisplayName(r.scientific_name))}</button><span>${(r.score * 100).toFixed(1)}% model score</span></div>`).join('')}<p class="subtle">The model ranks its 40 training labels and can suggest a name for a plant outside that list. For a web photo, verify the species against the original source and enter the scientific name below if the suggestions are incorrect.</p></div>`:''}
 <form id="profileForm"><div class="field-grid"><label>Plant name (scientific + common)<input name="scientific_name" id="speciesInput" list="plantNames" value="${esc(p.display_label||plantDisplayName(p.scientific_name)||p.plant_label)}" placeholder="e.g. Ocimum tenuiflorum (Holy Basil)" required><datalist id="plantNames">${plantCatalog.map(p=>`<option value="${esc(p.display_name)}">${esc(p.training_labels?.length?'Trained: '+p.training_labels.join(', '):'Reference profile only')} · ${esc(p.common_names.join(', '))}</option>`).join('')}</datalist><span id="plantNameHint" class="subtle">${system.model.classes?.length||0} training labels available; additional reference plants are labelled separately.</span></label><label>Plant part<select name="plant_part" id="profilePlantPart" required><option value="" disabled ${p.plant_part?'':'selected'}>Select plant part</option>${['leaves','root','bark','seed','flower','fruit','rhizome','whole plant'].map(x=>`<option ${p.plant_part===x?'selected':''}>${x}</option>`).join('')}</select></label><label class="span2">Target human disease / research indication<input name="target_disease" value="${esc(p.target_disease||'')}" placeholder="e.g. Type 2 diabetes — exploratory research" required></label><label class="span2">Confirming researcher<input name="researcher" value="${esc(p.researcher||'')}" placeholder="Your name" required minlength="2"></label><label class="span2">Collection & environmental notes<textarea name="collection_notes" rows="3" placeholder="Location, date, growing conditions, specimen limitations…">${esc(p.collection_notes||'')}</textarea></label></div><section id="partReferences" class="part-references" aria-live="polite"></section><div class="form-actions"><span>Save the plant profile as C1</span><button class="button primary">Save profile & continue →</button></div></form>`;
 $('imageInput').onchange=()=>busy(async()=>{const file=$('imageInput').files[0];if(!file)return;const f=new FormData();f.set('file',file);f.set('revision',current.revision);current=await api(`/api/cases/${current.id}/image`,{method:'POST',body:f});render();await refreshCases();toast('Specimen image saved.')});bind('predictButton', async () => {
   const part = $('profilePlantPart').value;
   if (!part) {
     $('profilePlantPart').focus();
     toast('Choose the plant part shown in the image.');
     return;
   }
   if (!isLeafPart(part) || !system?.model?.ready) {
     $('speciesInput').focus();
     toast('Enter the scientific name and review the references for this plant part.');
     return;
   }
   const draft = new FormData($('profileForm'));
   const caseId = current.id;
   const result = await api(`/api/cases/${caseId}/identify`, {
     method: 'POST', headers: {'Content-Type':'application/json'},
     body: JSON.stringify({revision:current.revision, plant_part:part}),
   });
   if (current.id !== caseId || step !== 1) return;
   current = result;
   render();
   const form = $('profileForm');
   for (const [name, value] of draft) form.elements.namedItem(name).value = value;
   $('speciesInput').dispatchEvent(new Event('input'));
   $('profilePlantPart').dispatchEvent(new Event('change'));
   await refreshCases();
   toast(result.identity_guidance?.message || 'Review the model suggestions and confirm the scientific name.');
 });
 $('speciesInput').addEventListener('input',()=>{const option=plantOption($('speciesInput').value);$('plantNameHint').textContent=option?.requires_scientific_confirmation?'You can save this label and test image quality. An exact scientific species will be needed for compound discovery.':option?.training_labels?.length?'Model training label: '+option.training_labels.join(', '):'Reference or manually entered plant; it may not be a trained image class.'});
 document.querySelectorAll('[data-prediction]').forEach(b=>b.onclick=()=>{$('speciesInput').value=current.prediction.predictions[+b.dataset.prediction].display_name||plantDisplayName(current.prediction.predictions[+b.dataset.prediction].scientific_name);$('speciesInput').dispatchEvent(new Event('input'))});
 setupPartReferences();
 $('profileForm').onsubmit=e=>{e.preventDefault();busy(async()=>{const values=Object.fromEntries(new FormData(e.target));values.scientific_name=plantScientificName(values.scientific_name);await mutate('profile',values);step=2;render();toast('C1 saved. Continue with specimen quality.')})};}
function setupPartReferences() {
 const form = $('profileForm');
 const panel = $('partReferences');
 const part = $('profilePlantPart');
 let timer, version = 0;

 function queueRefresh() {
   clearTimeout(timer);
   const requestVersion = ++version;
   const selectedPart = part.value;
   const predict = $('predictButton');
   if (predict) {
     predict.textContent = !selectedPart ? 'Choose the plant part →'
       : isLeafPart(selectedPart) && system?.model?.ready ? 'Suggest identity from leaf image ↗'
       : 'Review plant identity →';
   }
   const predictions = $('profilePredictions');
   if (predictions) predictions.hidden = selectedPart !== 'leaves';
   if (!selectedPart) {
     panel.innerHTML = '<p class="subtle">Select the part shown in the photo to see references.</p>';
     return;
   }
   panel.innerHTML = `<h4>References for ${esc(selectedPart)}</h4><p class="subtle">Looking up references…</p>`;

   timer = setTimeout(async () => {
     const values = new FormData(form);
     const query = new URLSearchParams({
       scientific_name: plantScientificName(values.get('scientific_name')),
       plant_part: selectedPart,
       target_disease: values.get('target_disease'),
     });
     try {
       const result = await api('/api/plant-part-references?' + query);
       if (!panel.isConnected || version !== requestVersion) return;
       renderPartReferences(panel, result);
     } catch (error) {
       if (!panel.isConnected || version !== requestVersion) return;
       panel.innerHTML = '<h4>Plant-part references</h4><p class="subtle">The catalog could not be loaded.</p>';
     }
   }, 250);
 }

 part.addEventListener('change', queueRefresh);
 form.elements.scientific_name.addEventListener('input', queueRefresh);
 form.elements.target_disease.addEventListener('input', queueRefresh);
 queueRefresh();
}

function renderPartReferences(panel, result) {
 const link = (url, label) => `<a href="${esc(safeURL(url))}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`;
 const images = result.images.map(image => `<li>${image.preview ? `<img class="part-reference-image" src="${esc(image.preview)}" alt="${esc(image.label)}">` : ''}${link(image.url, image.label)}</li>`).join('');
 const studies = result.studies.map(study => `<li>${link(study.url, study.label)}<p class="subtle">${esc(study.kind)} · ${esc(study.indication)}</p><p>${esc(study.note)}</p></li>`).join('');
 const example = !images && !studies && result.example_species.length
   ? `<p class="subtle">Catalog example for this part: ${esc(result.example_species.join(', '))}.</p>` : '';
 const lookup = result.search;
 panel.innerHTML = `<h4>References for ${esc(result.part)}</h4>
   ${result.part !== 'leaves' ? '<p class="subtle">Use the references and your own observations to record the identity. The image model is trained on leaves.</p>' : ''}
   ${!result.species ? '<p class="subtle">Enter a scientific species name to see matching references.</p>' : `
     <div class="field-grid">
       <div><strong>Image references</strong>${images ? `<ul>${images}</ul>` : '<p class="subtle">No curated image for this species and part.</p>'}${link(lookup.images, 'Search Wikimedia Commons')}</div>
       <div><strong>Part-specific research</strong>${studies ? `<ul>${studies}</ul>` : '<p class="subtle">No curated study for this species and part.</p>'}${link(lookup.research, 'Search PubMed')}${lookup.indication ? `<br>${link(lookup.indication, 'Search PubMed with your indication')}` : ''}</div>
     </div>`}
   ${example}`;
}

function isLeafPart(part) {
 return !part || ['leaf', 'leaves'].includes(part.trim().toLowerCase());
}

function needsPartQualityUpdate(result, part) {
 return Boolean(result && !isLeafPart(part) && !result.plant_part);
}

function bindLeafOutline(saved) {
 const editor = $('leafOutlineEditor');
 if (!editor) return () => null;
 const points = (saved || []).slice();
 const polygon = $('leafOutlinePolygon');
 function update() {
   polygon.setAttribute('points', points.map(([x,y]) => `${x * 100},${y * 100}`).join(' '));
   $('leafOutlinePoints').innerHTML = points.map(([x,y]) => `<circle cx="${x * 100}" cy="${y * 100}" r="0.6" fill="white" stroke="#163f33" stroke-width="0.25"/>`).join('');
   $('leafOutlineStatus').textContent = points.length >= 3 ? 'Outline ready to analyse.' : points.length ? `${points.length} points marked. Add at least 3.` : 'Automatic detection selected.';
   $('leafOutlineUndo').disabled = $('leafOutlineClear').disabled = !points.length;
 }
 editor.onclick = event => {
   if (points.length >= 80) return;
   const rect = editor.getBoundingClientRect();
   points.push([(event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height]
     .map(value => Math.max(0, Math.min(1, value))));
   update();
 };
 $('leafOutlineUndo').onclick = () => { points.pop(); update(); };
 $('leafOutlineClear').onclick = () => { points.length = 0; update(); };
 update();
 return () => {
   if (points.length && points.length < 3) throw Error('Mark at least three points around the leaf, or clear the outline.');
   return points.length ? points : null;
 };
}

function renderQuality() {
 const p = current.profile;
 const previous = current.quality;
 const needsRerun = needsPartQualityUpdate(previous, p.plant_part);
 const q = needsRerun ? null : previous;
 const leaf = isLeafPart(p.plant_part);
 let content;
 if (q) {
   const m = q.metrics;
   const flags = q.flags || [];
   const uncertainLeafArea = leaf && flags.some(flag => ['segmentation', 'framing'].includes(flag.code));
   const critical = flags.some(flag => flag.critical);
   const status = critical ? 'Retake photo' : flags.length || !leaf ? 'Review photo' : 'Suitable for visual review';
   const guidance = critical
     ? 'Address the retake flags before relying on the visual assessment. You can still look up documented compounds in Process 3.'
     : !leaf
       ? 'Inspect specimen condition in the original photo. The automated checks cover resolution, contrast and exposure.'
       : flags.length
         ? (uncertainLeafArea ? 'The detected area is uncertain. Review the original photo and retake it to measure leaf colour.' : 'Compare the highlighted areas with the original photo before interpreting them.')
         : 'Inspect the overlay to confirm the highlighted area follows the leaf.';
   const flagNames = {
     small_image: 'Low resolution', low_contrast: 'Low contrast', exposure: 'Dark photo',
     bright_exposure: 'Very bright photo', segmentation: 'Leaf hard to isolate',
     framing: 'Leaf area reaches frame edge', discoloration: 'Visible yellow or brown areas', blur: 'Photo detail',
   };
   const flagList = [...flags].sort((a,b) => Number(b.critical) - Number(a.critical)).map(flag =>
     `<li><span class="pill amber">${flag.critical ? 'Retake' : 'Review'}</span><div><strong>${esc(flagNames[flag.code] || 'Visual check')}</strong><p>${esc(flag.code === 'blur' ? 'The saved analysis flagged limited detail. Retake the photo in even lighting with the specimen clearly visible.' : flag.message)}</p></div></li>`).join('');
   const percent = value => value == null ? '—' : value + '%';
   const dimensions = `${m.image_width} × ${m.image_height} px`;
   const leafAreaLabel = q.outline ? 'Outlined leaf area (% of photo)' : 'Detected leaf area (% of photo)';
   const colourLabel = q.outline ? 'Yellow or brown (% of outlined area)' : 'Yellow or brown (% of detected leaf)';
   const metrics = leaf
     ? [[dimensions, 'Photo dimensions'], [percent(m.foreground_percent), uncertainLeafArea ? 'Detected area (% of photo, uncertain)' : leafAreaLabel], [uncertainLeafArea ? 'Unavailable' : percent(m.yellow_brown_percent), colourLabel]]
     : [[dimensions, 'Photo dimensions'], [percent(m.dark_pixel_percent), 'Very dark pixels'], [percent(m.bright_pixel_percent), 'Very bright pixels']];
   content = `<section class="quality-summary ${critical || flags.length || !leaf ? 'quality-attention' : ''}" aria-label="Suitability for visual review">
   <div class="panel-kicker">Suitability for visual review</div><h4>${status}</h4><p>${guidance}</p>
   ${flags.length ? `<ul class="quality-flags" aria-label="Suitability flags">${flagList}</ul>` : '<p class="quality-clear">No automated flags.</p>'}</section>
   <div class="image-pair"><figure><img src="${imageURL(p.image)}" alt="Original specimen"><figcaption>Original specimen</figcaption></figure>${q.overlay ? `<figure><img src="${imageURL(q.overlay)}" alt="Detected area overlay"><figcaption>${uncertainLeafArea ? 'Review the detected area. The overlay may include surrounding objects or miss part of the leaf.' : 'Green marks the detected leaf. Amber marks detected yellow or brown areas.'}</figcaption></figure>` : ''}</div>
   <div class="metrics">${metrics.map(([value, label]) => `<div class="metric"><b>${esc(value)}</b><small>${label}</small></div>`).join('')}</div>
   <details class="subtle"><summary>What these checks can tell you</summary><ul>${q.limitations.map(item => `<li>${esc(item)}</li>`).join('')}</ul></details>`;
 } else if (needsRerun) {
   content = `<div class="notice">The saved analysis used leaf measurements. Select Rerun analysis to check the ${esc(p.plant_part)} photo.</div>`;
 } else {
   content = `<div class="empty"><h2>Check your specimen photo</h2><p>${leaf ? 'Check whether the leaf is visible and framed clearly, and review any highlighted yellow or brown areas.' : 'Check resolution, contrast and exposure, then inspect the specimen in the original photo.'}</p></div>`;
 }
 $('processPanel').innerHTML = `<div class="section-top"><div><div class="panel-kicker">PROCESS 02 · C1 → C2</div><h3>${leaf ? 'Measure visual quality' : 'Check photo quality'}</h3><p class="subtle">${esc(p.display_label || plantDisplayName(p.scientific_name) || p.plant_label || 'Complete Process 1 first')} · ${esc(p.plant_part || 'specimen')}</p></div><span class="pill ${needsRerun || q?.flags.length ? 'amber' : ''}">${needsRerun ? 'RERUN NEEDED' : q ? 'ANALYSED' : 'PENDING'}</span></div>
 ${content}${leaf && p.image && p.confirmed ? `<details class="notice green"><summary>Outline the target leaf${q?.outline ? ' · saved outline' : ''}</summary>
 <p>Click around the edge of one leaf in order, then choose ${previous ? 'Rerun analysis' : 'Analyse specimen'}. The last point connects to the first.</p>
 <div class="leaf-outline-editor" id="leafOutlineEditor"><img src="${imageURL(p.image)}" alt="Specimen photo for tracing the target leaf" draggable="false"><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polygon id="leafOutlinePolygon" vector-effect="non-scaling-stroke"/><g id="leafOutlinePoints"></g></svg></div>
 <div class="leaf-outline-controls"><button type="button" class="button outline" id="leafOutlineUndo">Undo point</button><button type="button" class="button outline" id="leafOutlineClear">Clear outline</button><span id="leafOutlineStatus" aria-live="polite"></span></div></details>` : ''}
 <div class="form-actions"><span>Images do not reveal chemical purity.</span><button class="button primary" id="analyseButton" ${!p.confirmed || !p.image ? 'disabled' : ''}>${previous ? 'Rerun analysis' : 'Analyse specimen'} →</button></div>
 ${q ? '<button class="button outline full" id="nextDiscovery" style="margin-top:15px">Continue to phytochemical discovery →</button>' : ''}
 ${!p.confirmed || !p.image ? '<p class="subtle">Upload an image and confirm the plant in Process 1 to continue.</p>' : ''}`;
 const getOutline = bindLeafOutline(q?.outline);
 bind('analyseButton', async () => { await mutate('quality', {outline:getOutline()}); toast('Photo suitability assessment saved to C2.'); });
 bind('nextDiscovery', async () => { step = 3; render(); });
}
let discoveryPage=1, discoveryQuery='', discoveryView=null, discoveryCaseId=null;
function renderDiscovery(){
 const d=current.discovery,p=current.profile,f=d?.filters||{},coverage=d?.coverage,db=coverage?.database||system?.compound_database;
 if (needsPartQualityUpdate(current.quality, p.plant_part)) {
   $('processPanel').innerHTML = '<h3>Update specimen photo checks</h3><p>Rerun Process 2 for the selected plant part before continuing.</p><button class="button primary" id="updatePartQuality">Return to Process 2 →</button>';
   bind('updatePartQuality', async () => { step = 2; render(); });
   return;
 }
 if(p.species_confirmed===false){$('processPanel').innerHTML=`<div class="panel-kicker">PROCESS 03 · SPECIES CONFIRMATION NEEDED</div><h3>Choose an exact species for compound discovery</h3><p class="subtle">Your ${esc(p.display_label||p.plant_label||'plant')} case is saved. You can test image identification and visual quality with this label.</p><div class="notice">This training label does not identify one exact species. Compound discovery is paused so records from different plants are not mixed. Return to Process 1 and enter a confirmed scientific species when available.</div><button class="button primary" id="resolveSpecies">Return to plant profile →</button>`;bind('resolveSpecies',async()=>{step=1;render()});return;}
 if (discoveryCaseId !== current.id) {
   discoveryCaseId = current.id;
   discoveryPage = 1;
   discoveryQuery = '';
   discoveryView = null;
 }
 const view = discoveryView === 'selected' && !f.applied
   ? 'all'
   : discoveryView ?? (f.applied ? 'selected' : 'all');
 let rows=d?.compounds||[];
 if(discoveryQuery.trim()){const q=discoveryQuery.trim().toLowerCase();rows=rows.filter(c=>[c.name,c.smiles,c.inchikey,c.descriptors?.formula,...(c.alternative_names||[])].join(' ').toLowerCase().includes(q))}
 if(view==='selected')rows=rows.filter(c=>c.selected);
 if(view==='part')rows=rows.filter(c=>c.part_status==='reported_for_selected_part');
 const pages=Math.max(1,Math.ceil(rows.length/24));discoveryPage=Math.min(discoveryPage,pages);
 const shown=rows.slice((discoveryPage-1)*24,discoveryPage*24);
 $('processPanel').innerHTML=`<div class="section-top"><div><div class="panel-kicker">PROCESS 03 · C2 → C3</div><h3>Documented compounds for your plant</h3><p class="subtle">${esc(plantDisplayName(p.scientific_name)||'Unconfirmed species')} · selected part: ${esc(p.plant_part||'not supplied')}</p></div><span class="pill">${d?d.compounds.length+' STRUCTURES':'PENDING'}</span></div>
 <div class="notice green">Search every matching record in the installed database. No five-compound cap. Results describe documented species chemistry, not a complete laboratory analysis of this specimen.</div>
 <p class="subtle">${db?.ready?esc(db.release)+' · '+Number(db.occurrences).toLocaleString()+' referenced occurrences across '+Number(db.organism_labels).toLocaleString()+' organism labels.':'Compound database unavailable. Local references alone cannot provide broad coverage.'}</p>
 ${d&&!coverage?'<div class="notice">These are older demonstration results. Choose “Retrieve all documented compounds” to replace the five-record lookup for this case.</div>':''}
 ${coverage?.fallback?`<div class="notice green">Additional source: COCONUT · ${coverage.fallback.verified_taxon_records||0} exact-species records · ${coverage.fallback.complete?'source query complete':'partial source coverage'}${coverage.fallback.cache_used?' · cached':''}. Retrieved ${esc(coverage.fallback.retrieved_at||'not available')}.</div>`:''}
 ${coverage?.fallback&&!coverage.fallback.complete?`<details class="notice"><summary>Why is source coverage partial?</summary><p>The source advertised ${coverage.fallback.records_reported??'an unknown number of'} search hits. BIO-GEN recovered ${coverage.fallback.unique_candidates_retrieved??'an unknown number of'} unique candidates and verified ${coverage.fallback.verified_taxon_records??0} for this exact plant. Other candidate records can refer to similar plant names. ${coverage.fallback.unreconciled_search_hits!=null?coverage.fallback.unreconciled_search_hits+' source hits remain unreconciled.':''} Your verified results remain available; this is not an input error.</p></details>`:''}
 <form id="filterForm">
 ${coverage?.fallback?'<label class="check-label"><input type="checkbox" name="refresh_external"> Refresh external source (requires internet)</label>':''}
 <label class="check-label"><input type="checkbox" name="include_part_unverified" ${coverage?.include_part_unverified!==false?'checked':''}> Include species records whose plant part is unverified</label>
 <p class="subtle">Species-only database records do not establish the selected plant part. These records stay labelled “part unverified”; they are never presented as confirmed in your selected part.</p>
 <label class="check-label"><input type="checkbox" name="apply_property_filters" aria-describedby="propertyFilterHelp" ${f.applied?'checked':''}> Apply optional molecular-property filters</label>
 <p class="subtle" id="propertyFilterHelp">Set the limits and apply them to show matching compounds.</p>
 <div class="filters"><label>Maximum MW<input type="number" name="max_mw" value="${f.max_mw??750}" min="50" max="3000" step="any" required></label><label>Maximum LogP<input type="number" name="max_logp" value="${f.max_logp??7}" min="-10" max="20" step="any" required></label><label>Minimum QED<input type="number" name="min_qed" value="${f.min_qed??0}" min="0" max="1" step="any" required></label></div>
 ${current.production||Object.keys(current.production_runs||{}).length?'<p class="subtle">Rerunning compound discovery resets the current production results.</p>':''}
 <button type="submit" class="button primary full" id="retrieveCompounds" ${!current.quality?'disabled':''}></button></form>
 ${d?.recommendations_held?'<div class="notice">Recommendations held: a critical specimen-image issue remains. Database chemistry can still be explored.</div>':''}
 ${d?`<div class="metrics"><div class="metric"><b>${d.compounds.length}</b><small>Valid unique structures</small></div><div class="metric"><b>${d.part_supported_structures??'—'}</b><small>Selected-part support</small></div><div class="metric"><b>${d.invalid.length}</b><small>Unanalysed records retained</small></div></div>
 <p class="subtle">${Number(d.raw_records_retrieved??d.compounds.length).toLocaleString()} source structure records retrieved · ${d.duplicates.length} duplicate structures merged with their references. ${f.applied?d.compounds.filter(c=>c.selected).length+' meet optional filters.':'Property filters are off; all retrieved structures remain eligible for exploration.'} ${coverage?.matched_database_names?.length?'Database names matched: '+esc(coverage.matched_database_names.join('; '))+'.':''}</p>
 ${d.evidence_gaps.map(g=>`<div class="notice">${esc(g)}</div>`).join('')}
 <div class="browse-controls"><label>Search these results<input id="compoundSearch" value="${esc(discoveryQuery)}" placeholder="Name, formula, SMILES or InChIKey"></label><label>Show<select id="compoundView"><option value="all" ${view==='all'?'selected':''}>All compounds</option>${f.applied?`<option value="selected" ${view==='selected'?'selected':''}>Meet property filters</option>`:''}<option value="part" ${view==='part'?'selected':''}>Selected-part evidence</option></select></label></div>
 <div class="pagination"><span>${rows.length?'Showing '+((discoveryPage-1)*24+1)+'–'+Math.min(discoveryPage*24,rows.length)+' of '+rows.length:(view==='selected'&&!discoveryQuery.trim()?'No compounds meet these limits. Adjust the limits or choose All compounds.':'No compounds match this view')}</span><button class="button outline" id="prevCompounds" ${discoveryPage<=1?'disabled':''}>←</button><span>Page ${discoveryPage} / ${pages}</span><button class="button outline" id="nextCompounds" ${discoveryPage>=pages?'disabled':''}>→</button></div>
 <div class="compound-grid">${shown.map(c=>`<article class="compound"><div class="section-top"><h4>${esc(c.name)}</h4><span class="pill ${!c.selected?'amber':''}">${f.applied?(c.selected?'MEETS FILTERS':'FILTERED'):'DOCUMENTED'}</span></div>${c.svg}
 <span class="pill ${c.part_status!=='reported_for_selected_part'?'amber':''}">${c.part_status==='reported_for_selected_part'?'SELECTED-PART EVIDENCE':'PART UNVERIFIED'}</span>
 <div class="chemical-data"><span>MW <b>${c.descriptors.mw}</b></span><span>LogP <b>${c.descriptors.logp}</b></span><span>QED <b>${c.descriptors.qed}</b></span><span>TPSA <b>${c.descriptors.tpsa}</b></span></div><div class="chemical-data"><span>${esc(c.descriptors.formula)}</span><span>HBD ${c.descriptors.hbd}</span><span>HBA ${c.descriptors.hba}</span></div>
 <code>${esc(c.smiles)}</code><a href="${esc(safeURL(c.structure_source))}" target="_blank" rel="noopener">Structure source ↗</a>
 <details><summary>${(c.references||[]).length||1} evidence record(s)</summary>${(c.references?.length?c.references:[{source_url:c.source_url,source:'Reference'}]).map(r=>`<p><a href="${esc(safeURL(r.source_url))}" target="_blank" rel="noopener">${esc(r.source)} · ${esc(r.reported_species||p.scientific_name)} ↗</a><br><small>${r.plant_part?esc(r.plant_part):'Plant part unverified'}</small></p>`).join('')}</details>
 <p class="subtle">${esc(c.evidence_note||'')}${c.exclusion_reasons.length?' '+esc(c.exclusion_reasons.join('; ')):''}</p></article>`).join('')}</div>
 ${d.invalid.length?`<details class="notice"><summary>View ${d.invalid.length} records that could not be analysed</summary>${d.invalid.map(r=>`<p><b>${esc(r.name)}</b> · ${esc(r.reason)} · <a href="${esc(safeURL(r.source_url))}" target="_blank" rel="noopener">Source ↗</a></p>`).join('')}</details>`:''}
 <div class="form-actions"><span>Exports include all results, not just this page.</span><a class="button outline" href="/api/cases/${current.id}/compounds.csv">Download all compounds CSV ↗</a></div><button class="button outline full" id="continueToProduction">Continue to production simulation →</button>`:'<div class="empty"><span class="empty-symbol">◈</span><p>Retrieve all documented structures for this species, retain every reference, and calculate properties using IMPPAT and RDKit.</p></div>'}`;
 const form = $('filterForm');
 const applyFilters = form.elements.apply_property_filters;
 const propertyNames = ['max_mw', 'max_logp', 'min_qed'];
 function updateFilterControls() {
   for (const name of propertyNames) form.elements[name].disabled = !applyFilters.checked;
   $('retrieveCompounds').textContent = applyFilters.checked
     ? (d ? 'Apply property filters →' : 'Retrieve compounds and apply filters →')
     : 'Retrieve all documented compounds →';
 }
 applyFilters.onchange = updateFilterControls;
 updateFilterControls();
 form.onsubmit = event => {
   event.preventDefault();
   busy(async () => {
     const data = new FormData(form);
     const enabled = data.has('apply_property_filters');
     const values = {
       max_mw: enabled ? Number(data.get('max_mw')) : (f.max_mw ?? 750),
       max_logp: enabled ? Number(data.get('max_logp')) : (f.max_logp ?? 7),
       min_qed: enabled ? Number(data.get('min_qed')) : (f.min_qed ?? 0),
       apply_property_filters: enabled,
       include_part_unverified: data.has('include_part_unverified'),
       refresh_external: data.has('refresh_external'),
     };
     discoveryPage = 1;
     discoveryQuery = '';
     discoveryView = null;
     await mutate('discovery', values);
     const result = current.discovery;
     const message = result.filters.applied
       ? result.compounds.filter(compound => compound.selected).length + ' of ' + result.compounds.length + ' compounds meet the filters.'
       : 'C3 saved with ' + result.compounds.length + ' compounds.';
     toast(message + (result.coverage?.retrieval_complete_for_query ? '' : ' Source coverage is incomplete.'));
   });
 };

 if(d){
  $('compoundSearch').onchange=e=>{discoveryQuery=e.target.value;discoveryPage=1;renderDiscovery()};
  $('compoundView').onchange=e=>{discoveryView=e.target.value;discoveryPage=1;renderDiscovery()};
  bind('continueToProduction',async()=>{step=4;render()});
  bind('prevCompounds',async()=>{discoveryPage--;renderDiscovery()});
  bind('nextCompounds',async()=>{discoveryPage++;renderDiscovery()});
 }
}
async function example(){await newCase('Tulsi leaf · exploratory phytochemical case');const image=await fetch('/static/demo-tulsi.jpg');if(!image.ok)throw Error('Example image is not ready yet. Upload your own leaf image.');const f=new FormData();f.set('revision',current.revision);f.set('file',await image.blob(),'tulsi-reference.jpg');current=await api(`/api/cases/${current.id}/image`,{method:'POST',body:f});current=await api(`/api/cases/${current.id}/profile`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:current.revision,scientific_name:'Ocimum tenuiflorum',plant_part:'leaves',target_disease:'Exploratory phytochemical screening',researcher:'Example case — dataset label',identity_basis:'Dataset folder label Tulasi; not an independent botanical authentication',source_url:'https://doi.org/10.17632/748f8jkphb.3',collection_notes:'Example image from the CC BY 4.0 medicinal-leaf dataset. Source label used for a reproducible demonstration.'})});render();await refreshCases();toast('Sourced example loaded. Run Process 2 to inspect the leaf.')}
$('newCase').onclick=()=>$('newDialog').showModal();$('newForm').onsubmit=e=>{e.preventDefault();busy(async()=>{await newCase(new FormData(e.target).get('title'));$('newDialog').close();e.target.reset()})};
$('reviewButton').onclick=()=>$('reviewDialog').showModal();$('reviewForm').onsubmit=e=>{e.preventDefault();busy(async()=>{await mutate('reviews',Object.fromEntries(new FormData(e.target)));$('reviewDialog').close();e.target.reset();toast('Review recorded with the current case stage.')})};
$('exportButton').onclick=()=>{if(current)window.open(`/api/cases/${current.id}/report`,'_blank','noopener')};$('aboutButton').onclick=()=>$('aboutDialog').showModal();
document.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>{step=+b.dataset.step;render()});
(async()=>{try{[system,plantCatalog]=await Promise.all([api('/api/status'),api('/api/plant-options')]);$('plantCount').textContent=plantCatalog.length;$('modelState').textContent=system.model.ready?'Ready':'Manual entry';const caseId=new URLSearchParams(location.search).get('case');if(caseId&&/^[a-f0-9]{32}$/.test(caseId)){current=await api('/api/cases/'+caseId);step=Math.max(1,Math.min(4,Number(current.stage.slice(1))))}render();await refreshCases()}catch(e){toast(e.message,true)}})();
