# BIO-GEN

An implemented research proof of concept connecting the first three processes of the BIO-GEN overview:

**C0 initial case → C1 plant and disease profile → C2 visual quality results → C3 documented compounds and molecular triage.**

## Set up a fresh GitHub clone

```powershell
git clone https://github.com/Osamahfm/BIO-GEN.git
cd BIO-GEN
.\setup.ps1 -Python python
.\.venv\Scripts\python.exe scripts\download_lotus.py
.\.venv\Scripts\python.exe scripts\index_lotus.py
.\start.ps1
```

Use Python 3.12. The trained identification checkpoint is included in `models/plant_model.pt`, together with its evaluation and split records. Third-party source snapshots and licenses are bundled in `vendor/`; no submodule checkout is required.

The local Python environment, downloaded training images, saved research cases, logs, caches, and large LOTUS download/index files are excluded from Git. The commands above retrieve the pinned LOTUS release and rebuild its index before the first full compound lookup. See [compound retrieval](docs/COMPOUND_RETRIEVAL.md) and [third-party notices](THIRD_PARTY_NOTICES.md) for provenance and dataset details.

## Open the application

Double-click **Start BIO-GEN.cmd**, or run `./start.ps1` from this folder.

Visit **http://127.0.0.1:8765**. The initial environment is already installed locally. The launcher starts a hidden local server and opens your browser, or reuses the existing BIO-GEN server. Use **Stop BIO-GEN.cmd** to stop it; saved cases remain on disk.

The app runs on your computer. No account, hosted LLM, cloud database, or API key is required for the included workflow. The setup and reference refresh scripts require internet access.

## Try the demonstration

1. Choose **Explore a sourced Tulsi example** on the welcome screen. It creates a case with an attributed dataset photograph and an explicitly labelled dataset-based identity.
2. In **Process 1**, optionally run **Suggest plant identity**. Review model suggestions; the researcher confirms the actual identity, plant part and target human disease. The target disease is context, not a therapeutic prediction.
3. In **Process 2**, choose **Analyse specimen**. Inspect the foreground overlay and the recorded visual indicators.
4. In **Process 3**, choose **Retrieve all documented compounds**. The complete installed LOTUS release is queried for your species. Inspect every retrieved structure, its references and plant-part evidence. Property filters are optional and off by default; pagination only affects the display.
5. Record a review. Export the printable report, compound CSV, or complete JSON history.
6. Reload and select the saved case in the sidebar. Every revision remains in the local SQLite database.

An example case created during interface verification is already saved. Its automated review notes are explicitly labelled as verification, not expert approval.

## What is implemented

- A custom responsive BIO-GEN interface with case creation and reopening.
- Immutable case snapshots in SQLite; atomic transitions reject stale edits.
- Original Ayur-Ai knowledge-base retrieval and checkpoint inference.
- An actual trained 40-label ResNet18 identification model. The architecture and checkpoint utilities come from Ayur-Ai; BIO-GEN trains its classification head on public images.
- PlantCV saturation thresholding and colour analysis, combined with OpenCV segmentation and sharpness checks.
- Direct execution of the original IMPPAT2 `MolecularProperties.py` script on real chemical structures.
- Structure validation, canonical SMILES deduplication, molecular images, property filters, and QED annotations.
- Full LOTUS species lookup, taxon-aware matching, retained references, explicitly unverified plant parts, and separately supported part-specific records.
- Evidence links, review records, unresolved flags, and recommendation holds for critical image-quality failures.
- Printable reports, CSV downloads and JSON exports including all saved revisions.
- Invalidating downstream analyses when the image or confirmed profile changes.

## Measured model performance

On the downloaded dataset: **5,945 images, 40 dataset labels**. Perceptual-hash groups were kept together before splitting: 4,152 training / 891 validation / 902 test images. The frozen-backbone classification head reached **84.59% accuracy and 0.8454 macro F1 on the internal test split**. Selection used validation loss, not the test set.

These are internal prototype results. They do not establish field performance or independent specimen-level generalization. Collection/site leakage may remain despite perceptual-hash grouping. Scores are uncalibrated; unsupported species can receive confident incorrect labels. The knowledge base has 30 profiles, whereas the image model has 40 dataset labels. They are separate resources, and not every image label has an authenticated botanical mapping.

Details: [model report](models/identification.json), [split manifest](models/split-manifest.json), and [model documentation](docs/MODEL.md).

## Scientific scope and limits

- The image model classifies dataset plant labels. It is **not a trained plant-disease classifier**.
- Visual colour, sharpness and segmentation are measured; health/quality flags use prototype thresholds. Fully discoloured tissue or complex backgrounds may invalidate the mask.
- No chemical purity, phytochemical concentration, compound presence in this specimen, clinical efficacy, or patient safety is established.
- The installed LOTUS release provides broad species-level coverage. Its 37,469 organism labels include non-plant organisms. Plant part is unverified unless separately supported by the curated references. Missing records remain explicit evidence gaps; database coverage is not chemical completeness.
- Candidate selection is **physicochemical filtering**, not NSGA-II, MOBO, target-binding prediction or therapeutic optimization. Those remain later components.
- Reviews are recorded as supplied. Reviewer credentials are not authenticated. A review note does not silently clear measured image failures.
- The implemented retrieval is Ayur-Ai's offline TF-IDF search, not a complete evidence-grounded LLM/RAG system.
- Processes 4–10 are not implemented in this milestone.

## Project layout

- `biogen/`: original BIO-GEN backend, process adapters, persistence and reports.
- `static/`: original BIO-GEN interface and attributed example photograph.
- `vendor/ayur-ai/`: upstream source and MIT license.
- `vendor/imppat2/`: upstream source and MIT license.
- `.venv/`: isolated local Python dependencies, including PlantCV.
- `models/`: trained checkpoint, evaluation, training history and split records.
- `data/reference/`: independently curated associations and PubChem structure responses.
- `data/cases/`: saved cases and uploaded/analysed images; excluded from version control.
- `scripts/`: training, reference preparation, catalog import and browser verification.
- `tests/`: real component and case-transition checks.
- `docs/`: provenance, verification results and interface screenshots.

## Reproduce and extend

Python 3.12 was used. For a clean environment run `setup.ps1 -Python <path-to-python>`. The exact installed versions are in `requirements-lock.txt`; CPU PyTorch can be installed from `https://download.pytorch.org/whl/cpu`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts\prepare_reference.py
.\.venv\Scripts\python.exe scripts\train_identification.py --threads 4 --epochs 150
```

To add other plants, fill `data/reference/import-template.csv` with independently sourced plant-part associations and verified SMILES, then run:

```powershell
.\.venv\Scripts\python.exe scripts\import_compounds.py your-records.csv
```

Do not treat an unknown plant as having no phytochemicals. Do not merge a plant's root associations into a leaf case. Add evidence instead.

See [third-party notices](THIRD_PARTY_NOTICES.md), [model provenance](docs/MODEL.md), and [milestone acceptance](docs/MILESTONE.md).

## Expanded compound retrieval

Process 3 uses LOTUS 2026-04-13 (674,454 occurrence records / 227,298 structure entries), with no five-compound cap. Verified examples: Tulsi 106, Neem 449, spearmint 195 valid unique structures; mango 770 valid plus one unanalysed source record retained. These are source-coverage counts, not measured specimen composition. See [compound retrieval documentation](docs/COMPOUND_RETRIEVAL.md).

If a species is absent from LOTUS, Process 3 can use a COCONUT fallback with exact-species verification and a local cache. The initial lookup requires internet. A source with overlapping or incomplete pages is labelled incomplete, even when verified compounds can be displayed. Use Refresh external source to retry; do not interpret the retrieved count as chemical completeness.

## Plant dropdown coverage

The dropdown now uses a shared catalog containing all 40 model labels and the original 30 reference profiles (57 merged choices). Common names are shown in brackets. Training labels and reference-only choices are explicitly distinguished. The same catalog names image predictions. Broad/ambiguous class labels can be saved as label-only profiles and used for image-quality testing. Exact species remains unconfirmed, so compound discovery is held until a researcher supplies a species. They are not silently assigned to a different plant. Suggested mappings do not independently authenticate the training photos.
