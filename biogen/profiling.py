"""Adapter to the unmodified, MIT-licensed Ayur-Ai modules."""
import json
import sys
from functools import lru_cache

from .settings import AYUR, MODELS

sys.path.insert(0, str(AYUR))
from src.nlp.knowledge_base import KnowledgeBase
from src.nlp.retriever import PlantRetriever


@lru_cache
def knowledge():
    return KnowledgeBase.load(AYUR / 'data/knowledge_base/plants.json')


@lru_cache
def retriever():
    return PlantRetriever(knowledge())


def plants(query=''):
    if query.strip():
        return [dict(h.plant.to_dict(), relevance=round(h.score, 4)) for h in retriever().query(query, top_k=10)]
    return [p.to_dict() for p in knowledge().plants]


def model_status():
    path = MODELS / 'identification.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
        'ready': False, 'message': 'Image classifier not trained yet. Confirm the scientific name manually.'}


@lru_cache(maxsize=2)
def predictor(mtime):
    import torch
    from src.config import Config
    from src.predict import LeafPredictor
    torch.set_num_threads(4)
    return LeafPredictor(cfg=Config.load(), checkpoint=str(MODELS / 'plant_model.pt'), device='cpu')


def has_green_tissue(path):
    """Conservative color screen for leaf inference, not a plant-part detector."""
    import cv2
    import numpy as np
    from PIL import Image

    with Image.open(path) as source:
        image = source.convert('RGB')
        image.thumbnail((640, 640))
        hsv = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2HSV)
    hue, saturation, brightness = cv2.split(hsv)
    green = (hue >= 35) & (hue <= 100) & (saturation > 45) & (brightness > 35)
    return float(green.mean()) >= 0.03


def identify(path):
    checkpoint = MODELS / 'plant_model.pt'
    if not checkpoint.exists():
        raise ValueError('No trained identification model is available. Use manual species confirmation.')
    result = predictor(checkpoint.stat().st_mtime_ns).predict(path, topk=3)
    from .plant_catalog import label_info
    labels = {p.label: label_info(p.label) for p in result}
    return {'model': model_status(), 'predictions': [
        {'label': p.label, 'score': round(p.confidence, 5),
         'scientific_name': (labels[p.label] or {}).get('botanical_name') or p.label,
         'display_name': (labels[p.label] or {}).get('display_name') or p.label,
         'requires_scientific_confirmation': (labels[p.label] or {}).get('requires_scientific_confirmation', True),
         'knowledge_base_match': (labels[p.label] or {}).get('reference_profile', False)} for p in result],
        'limitation': 'Uncalibrated model scores; unsupported species can receive a confident incorrect label. Researcher confirmation is required.'}
