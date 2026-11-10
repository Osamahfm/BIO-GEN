"""Validated molecular analysis over the complete installed species-reference lookup."""
import csv
import io
import subprocess
import sys
import tempfile
from rdkit import Chem
from rdkit.Chem import Draw, QED
from .settings import IMPPAT
from .plant_compounds import retrieve


def analyse_compounds(records,max_mw=750,max_logp=7,min_qed=0,apply_property_filters=True):
    accepted=[];invalid=[];duplicates=[];seen={}
    for record in records:
        smiles=record.get('smiles','')
        mol=Chem.MolFromSmiles(smiles) if smiles else None
        if mol is None or not mol.GetNumAtoms():
            invalid.append(dict(record,reason='Invalid SMILES' if smiles else 'No molecular structure supplied by source'))
            continue
        canonical=Chem.MolToSmiles(mol,isomericSmiles=True)
        if canonical in seen:
            duplicates.append(record.get('name',''))
            previous=accepted[seen[canonical]][0]
            refs=previous.setdefault('references',[])
            for ref in record.get('references',[]):
                if ref not in refs: refs.append(ref)
            aliases=previous.setdefault('alternative_names',[])
            if record.get('name') and record['name']!=previous['name'] and record['name'] not in aliases:
                aliases.append(record['name'])
            if record.get('part_status')=='reported_for_selected_part':
                for field in ('name','plant_part','part_status','source_url','evidence_note','evidence_type'):
                    if field in record: previous[field]=record[field]
            continue
        seen[canonical]=len(accepted)
        accepted.append((dict(record,smiles=canonical),mol))
    if not accepted: return {'compounds':[],'invalid':invalid,'duplicates':duplicates}
    with tempfile.TemporaryDirectory(prefix='biogen-chem-') as tmp:
        from pathlib import Path
        source,output=Path(tmp)/'input.smi',Path(tmp)/'properties.tsv'
        source.write_text(''.join(f'{r["smiles"]}\t{i}\n' for i,(r,_) in enumerate(accepted)),encoding='utf-8')
        run=subprocess.run([sys.executable,str(IMPPAT/'CODES/MolecularProperties.py'),'smiles',str(source),str(output)],capture_output=True,text=True,timeout=180)
        if run.returncode: raise RuntimeError('IMPPAT descriptor calculation failed: '+run.stderr[-500:])
        rows=list(csv.DictReader(io.StringIO(output.read_text(encoding='utf-8')),delimiter='\t'))
    calculated=[];returned=set()
    for row in rows:
        index=int(row['Identifier']);returned.add(index)
        record,mol=accepted[index]
        mw,logp,tpsa=float(row['Mol.wt']),float(row['LogP']),float(row['Topological polar surface area '])
        hbd,hba=int(row['Number of Hydrogen bond donors']),int(row['Number of Hydrogen bond acceptors'])
        qed=float(QED.qed(mol));reasons=[]
        if apply_property_filters:
            if mw>max_mw: reasons.append('Molecular weight exceeds selected limit')
            if logp>max_logp: reasons.append('LogP exceeds selected limit')
            if qed<min_qed: reasons.append('QED below selected limit')
        violations=sum([mw>500,logp>5,hbd>5,hba>10])
        svg=Draw.MolsToGridImage([mol],molsPerRow=1,subImgSize=(250,170),useSVG=True)
        calculated.append(dict(record,descriptors={'mw':round(mw,2),'logp':round(logp,3),'tpsa':round(tpsa,2),'hbd':hbd,'hba':hba,'qed':round(qed,4),'lipinski_violations':violations,'formula':row['Chemical formula']},selected=not reasons,exclusion_reasons=reasons,svg=str(svg)))
    for i,(record,_) in enumerate(accepted):
        if i not in returned: invalid.append(dict(record,reason='Descriptor engine did not return this structure'))
    return {'compounds':calculated,'invalid':invalid,'duplicates':duplicates}


def discover(scientific_name,plant_part,max_mw=750,max_logp=7,min_qed=0,apply_property_filters=False,include_part_unverified=True,refresh_external=False):
    records,coverage=retrieve(scientific_name,plant_part,include_part_unverified,refresh_external)
    result=analyse_compounds(records,max_mw,max_logp,min_qed,apply_property_filters)
    gaps=list(coverage['warnings'])
    if not records:
        if not include_part_unverified:
            gaps.append('No selected-part records are available. Enable species records with unverified plant part to search broader species chemistry.')
        elif coverage.get('fallback') and not coverage['fallback'].get('complete'):
            gaps.append('No compounds are available yet because the external-source lookup was incomplete. This is a retrieval issue, not evidence of chemical absence.')
        else:
            gaps.append('No exact-species records were found in the consulted LOTUS/COCONUT sources. Check the scientific name or add referenced records; this does not establish chemical absence.')
    if any(c.get('part_status')=='unverified' for c in result['compounds']):
        gaps.append('Some database occurrences are reported for the species without a plant part. They are not verified for the selected part or specimen.')
    if result['invalid']: gaps.append(f'{len(result["invalid"])} source structures could not be analysed; their records and references are retained separately.')
    return dict(result,engine='LOTUS occurrence lookup + COCONUT fallback + original IMPPAT2 MolecularProperties.py + RDKit',
                filters={'max_mw':max_mw,'max_logp':max_logp,'min_qed':min_qed,'applied':apply_property_filters},
                coverage=coverage,raw_records_retrieved=len(records),
                part_supported_structures=sum(c.get('part_status')=='reported_for_selected_part' for c in result['compounds']),
                evidence_status='literature_reported_not_measured_in_specimen',
                note='All available matching database records are retrieved. Optional property filters do not remove source records.',
                evidence_gaps=gaps)
