# Identification model: reproducible prototype

The initial model was actually trained during project setup, rather than using random or fabricated prediction values.

- Architecture and checkpoint loader: original Ayur-Ai ResNet18 implementation.
- Initialization: torchvision ImageNet pretrained backbone; backbone frozen.
- Inputs: RGB photos resized to 160 × 160 with ImageNet normalization.
- Training: cached backbone features, a dropout/linear head, AdamW optimizer, cross-entropy objective, 150 epochs, seed 42. Best head selected by validation loss.
- Source archive: `data/downloads/medicinal-leaves.zip` from the attributed CC BY 4.0 Kaggle mirror; see the notices for original Mendeley authors and DOI.
- Archive extracted safely into `data/training/leaves/` using only each species folder and image filename.
- Data: 5,945 original archive images / 40 dataset labels.
- Split: Ayur-Ai's perceptual-hash connected components kept within one subset, threshold 8; 4,152 training, 891 validation, 902 test images.
- Internal test accuracy: 84.5898%; macro F1: 0.845357.
- Runtime for the recorded training run: 246.7 seconds on this machine, including preparation and feature extraction. This is not a promised runtime on other computers.

Artifacts:

- `models/plant_model.pt`: actual trained weights (loaded with PyTorch `weights_only=True`).
- `models/identification.json`: class list, per-class metrics, confusion matrix, model checksum and limitations.
- `models/training-history.json`: recorded validation history.
- `models/split-manifest.json`: exact relative image paths in each subset.

Re-run with `./.venv/Scripts/python.exe scripts/train_identification.py --threads 4 --epochs 150` after downloading the source dataset. Initial ImageNet weight download requires internet; subsequent inference is local.

## Interpretation limits

Perceptual hashes reduce near-duplicate leakage, but do not establish plant-level or site-level independence. Source images may show the same plant and background. The internal test is not a field trial, independent external validation, or authentication of medicinal species. The archive contains photographs of plants/leaves, sometimes with soil, pots and background cues. Background shortcuts remain a material risk.

The image model has 40 dataset labels, while the educational knowledge base has 30 plant profiles. Common names can be ambiguous. A shared catalog now includes every one of the 40 training labels plus the 30 reference profiles, merging matching entries. Common-name mappings suggest identities; broad or ambiguous labels remain explicitly unresolved. The researcher must confirm the scientific identity. No fuzzy knowledge-base match is treated as botanical confirmation.

Model scores are not calibrated probabilities of correct identification. Low scores do not detect every unsupported species, and a high score does not authenticate a specimen. The model does not classify disease, stress, extraction suitability, chemical composition or toxicity.

## Next useful improvements

Obtain independent specimen-level field images, add a defensible unknown-image rejection method, calibrate scores on separate data, check per-class failures, and fine-tune the backbone with a documented validation protocol. Add medicinal-plant disease/quality labels before claiming specific disease diagnosis.

Label-only testing: broad training labels can be saved in a case and used for visual-quality testing. The scientific-name field stays empty, species_confirmed is false, and compound discovery is held. Supplying an exact species later creates a new revision and invalidates dependent outputs.
