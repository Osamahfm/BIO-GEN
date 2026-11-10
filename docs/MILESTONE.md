# Proof-of-concept milestone: 10 November 2026

This is a demonstration of the first three connected processes. Completion percentage should be agreed against the team's implementation backlog; three partially implemented processes are not automatically 30% of the full platform.

## Working acceptance criteria

- Create a persistent case and reopen it after a page reload.
- Upload a valid specimen image; reject invalid files.
- Run actual model inference and require researcher identity confirmation.
- Save target human disease context separately from any plant visual condition.
- Produce C1, C2 and C3 while preserving previous information and immutable revisions.
- Run actual PlantCV colour analysis and display the inspected segmentation overlay.
- Keep image-quality failures visible; critical failures hold recommendations.
- Retrieve every matching record from the installed LOTUS release, retain its evidence, and distinguish species-only records from selected-part support.
- Run the original IMPPAT descriptor script on validated molecular structures.
- Remove duplicate canonical structures and explain filter exclusions.
- Record review outcomes without claiming authenticated expert approval.
- Export a printable report, compound CSV and complete case/history JSON.
- Reject stale edits and invalidate downstream outputs after upstream changes.

## Verification performed

Fourteen backend tests passed against actual PlantCV/IMPPAT/retrieval components. A browser walkthrough checked the C1 → C2 → C3 flow, full species-retrieval results, changed filtering, saved review, JSON history export, reopening, and mobile overflow. See `interface-verification.json` and screenshots.

The image classifier has an actual recorded internal evaluation; see `models/identification.json`. Its performance is not a claim of clinical, pharmacological, specimen-level or field validation.

## Team contributions to present

Present the original case architecture, connected adapters, custom interface, review/provenance tracking, property-triage logic, independently curated reference records and verification. Acknowledge the reused architecture, original IMPPAT script and PlantCV toolkit by name.

## Still outside this implementation

Specific plant-disease diagnosis; experimentally measured specimen chemistry; target-specific therapeutic prediction; automated expert authentication; full evidence-grounded RAG/LLM review; the shared multi-objective optimizer; genetic/production simulation; formulation; nonclinical simulation; clinical-trial simulation; and regulatory readiness. These remain on the full-year roadmap.
