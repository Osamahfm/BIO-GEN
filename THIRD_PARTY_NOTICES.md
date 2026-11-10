# Attribution and reuse

## Ayur-Ai

- Repository: https://github.com/Jitheswar/Ayur-Ai
- Snapshot: `7f2ef089ea4d7a3da6b5cd7e29bb3d478ddab1f8`
- Copyright (c) 2026 Jitheswar; MIT.
- Full notice preserved at `vendor/ayur-ai/LICENSE`.
- BIO-GEN imports the original knowledge base, TF-IDF retriever, inference transforms, model architecture and checkpoint utilities. The original knowledge text is educational and is not independently validated medical evidence. It is not used to generate treatment recommendations.
- Upstream source is retained unmodified. BIO-GEN's interface, adapters, persistence and training orchestration are separately implemented in this project.

## IMPPAT2 analysis code

- Repository: https://github.com/asamallab/IMPPAT2
- Snapshot: `edb740833b7330b1d8a8f5ffd5a1674e5e175b9b`
- MIT; full notice preserved at `vendor/imppat2/LICENSE.md`.
- Original `CODES/MolecularProperties.py` is invoked without modification. BIO-GEN adds validation, per-case structure deduplication, interactive filters, reports and additional RDKit QED annotations.
- Cite: Vivek-Ananth et al., *IMPPAT 2.0: an enhanced and expanded phytochemical atlas of Indian medicinal plants*, ACS Omega 8(9):8827–8845, 2023. https://doi.org/10.1021/acsomega.3c00156
- The IMPPAT database is **not bundled**. The MIT code license does not grant unrestricted rights to database contents. The current website lists separate database terms at https://cb.imsc.res.in/imppat/download .

## PlantCV

- Repository: https://github.com/danforthcenter/plantcv
- Installed version: 4.11.3; MPL-2.0. Installed as an unmodified dependency in `.venv`.
- Source and license: https://github.com/danforthcenter/plantcv/blob/main/LICENSE
- Used directly for binary saturation thresholding, small-object removal and colour observations. BIO-GEN adds image-quality checks, a green-anchored OpenCV GrabCut mask and case records.
- Relevant publications: https://plantcv.danforthcenter.org/#plantcv-publications

## Training images and example image

- Dataset original credit: B R, Pushpa; Rani, Shobha (2023), *Indian Medicinal Leaves Image Datasets*, Mendeley Data V3. https://doi.org/10.17632/748f8jkphb.3
- Downloaded mirror: https://www.kaggle.com/datasets/warcoder/indian-medicinal-plant-image-dataset
- The mirror declares CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- The downloaded archive contains 5,945 images in 40 labelled folders. This measured content differs from the mirror's 80-variety description. Do not report 80 trained classes.
- `static/demo-tulsi.jpg` is the unmodified archive image `Medicinal plant dataset/Tulasi/261.jpg`. Its dataset label is not an independently verified botanical identification.
- The model uses torchvision's public ImageNet ResNet18 backbone weights, with a BIO-GEN-trained classification head. This does not grant rights beyond the underlying component/data terms.

## Molecular references

- Structure source: NCBI PubChem PUG REST; raw response in `data/reference/pubchem-response.json` and per-compound structure links retained in the catalog.
- Eugenol CID 3314; rosmarinic acid CID 5281792; ursolic acid CID 64945; apigenin CID 5280443; linalool CID 6549.
- Tulsi eugenol/rosmarinic-acid evidence: https://pubmed.ncbi.nlm.nih.gov/42064634/ . Other starter associations are explicitly review-reported: https://pmc.ncbi.nlm.nih.gov/articles/PMC11521583/ .
- Records are independently curated demonstration facts and links, not an IMPPAT export. No full article text is bundled. Revisit primary methods and species/part matching before scientific use.

## Other dependencies

RDKit, OpenCV, PyTorch, torchvision, scikit-learn, FastAPI and their dependencies retain their own licenses and notices. Exact installed versions are recorded in `requirements-lock.txt`. Redistributing a packaged environment requires retaining the relevant dependency notices.

The BIO-GEN project must acknowledge reused components in its proposal and demonstration. Renaming an upstream model or interface does not make that upstream work the team's original contribution.

## LOTUS full occurrence release

The LOTUS Initiative, frozen export 2026-04-13, Zenodo record 19360665: https://doi.org/10.5281/zenodo.19360665 . Cite Rutz et al., The LOTUS initiative for open knowledge management in natural products research, eLife 2022: https://doi.org/10.7554/eLife.70780 . This downloaded release declares CC BY 4.0 in its Zenodo metadata. Full release metadata, file checksums, organism associations and source references are preserved under data/reference/lotus/. Species-level records do not establish plant-part or specimen-level presence.

## COCONUT lookup fallback

Public organism search and exact-taxonomic annotations from COCONUT: https://coconut.naturalproducts.net/ . Each cached result retains its compound URL, source timestamp and JSON-LD license annotation. Compound-level database citations are not automatically treated as evidence of that compound in a particular plant part. Consult the original linked database record and contributing collection terms before scientific use or redistribution.
