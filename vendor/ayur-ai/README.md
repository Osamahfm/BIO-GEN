# Ayur-Ai

Take a photo of an Ayurvedic medicinal leaf and this tells you which plant it is, then looks up what the plant is used for. It runs fully offline, with no LLM and no API keys.

> Educational project. The medicinal information comes from common Ayurvedic and ethnobotanical references and is for learning and identification only. It is not medical advice.

| Step | What it does | How |
|---|---|---|
| 1. Identify | Names the plant from a leaf photo | ResNet18 fine-tuned in PyTorch |
| 2. Look up | Finds its medicinal properties, or finds herbs matching a symptom | TF-IDF search over a herb knowledge base (scikit-learn) |

## How well it works

Trained on the Mendeley Medicinal Leaf Dataset: 30 species, 1,835 images.

Many photos in that dataset show the same physical leaf. To stop the model from being tested on leaves it has already seen, near-duplicate images are grouped and each group goes entirely into one split.

| | Result |
|---|---|
| 5-fold cross-validation (the headline number) | 98.64% accuracy, macro F1 0.9849 |
| Served model, single split (seed 42) | 99.28% accuracy (275 of 277) |
| Training time | about 2 minutes on an RTX 3050 6 GB |

A single split swings between about 0.87 and 1.00 depending on the seed (see `experiments/multiseed.jsonl`), which is why cross-validation is the number to trust.

To reproduce: `python -m src.train`, then `python -m src.evaluate` for the served model, or `python -m experiments.cv_eval --k 5 --seed 42` for the cross-validation figure.

## Setup

Use Python 3.11 or 3.12. PyTorch has no wheels for 3.14 yet.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The herb search works right away, before you have any data or model:

```bash
python -m src.nlp.retriever
```

## Get the data

Download the Mendeley "Medicinal Leaf Dataset" (30 species, from S. Roopashree). Its folder names already match the knowledge base. Kaggle's "Indian Medicinal Leaves Image Datasets" also works.

Put it in `data/raw/`, one folder per plant:

```
data/raw/
├── Ocimum Tenuiflorum (Tulsi)/   img001.jpg img002.jpg ...
├── Azadirachta Indica (Neem)/    img001.jpg ...
└── ...
```

Check the layout, and see which classes are missing from the knowledge base:

```bash
python scripts/check_data.py
```

## Train, evaluate, predict

```bash
python -m src.train                                        # defaults from config.yaml
python -m src.train --backbone efficientnet_b0 --epochs 30
python -m src.train --freeze-backbone                      # head only: fast, good for little data
python -m src.evaluate                                     # per-class metrics and confusion matrix
python -m src.predict path/to/leaf.jpg --topk 3            # top guesses plus medicinal info
```

Other backbones: `resnet18` (default), `resnet50`, `mobilenet_v2`, `efficientnet_b0`. The best model is saved to `models/best_model.pt`. Plots and metrics go to `outputs/`.

## Web app

```bash
streamlit run app.py
```

- **Identify a leaf:** upload a photo, get the species and its properties
- **Search by symptom:** type "cough and cold" and get a ranked list of herbs
- **Browse herbs:** look through all 30

Search and Browse work before you train anything.

## How the search works

For each herb it builds one block of text from its names, properties, uses and description, and turns that into TF-IDF vectors. Your query is turned into a vector the same way, and herbs are ranked by cosine similarity. It's old-school information retrieval: fast, offline and easy to explain.

To add herbs, add entries to `data/knowledge_base/plants.json` with the same fields. The `folder_aliases` field links a classifier class name to its herb entry.

## Settings

Everything lives in [`config.yaml`](config.yaml): image size, splits, batch size, backbone, learning rate, epochs, early stopping and the knowledge base path. Any value can be overridden on the command line (`python -m src.train --help`).
