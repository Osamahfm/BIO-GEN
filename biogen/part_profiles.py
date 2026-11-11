"""Curated image and research references keyed by scientific species and plant part."""
import json
from functools import lru_cache
from urllib.parse import urlencode

from .settings import ROOT


PART_TERMS = {
    'leaves': ('leaf', 'leaves'),
    'root': ('root', 'roots'),
    'bark': ('bark',),
    'seed': ('seed', 'seeds'),
    'flower': ('flower', 'flowers'),
    'fruit': ('fruit', 'fruits'),
    'rhizome': ('rhizome', 'rhizomes'),
    'whole plant': ('whole plant', 'entire plant'),
}


def normalize_part(value):
    part = ' '.join(value.lower().split())
    return next((key for key, terms in PART_TERMS.items() if part in terms), part)


def species_key(name):
    key = ' '.join(name.casefold().split())
    return 'ocimum tenuiflorum' if key == 'ocimum sanctum' else key


@lru_cache
def catalog():
    path = ROOT / 'data/reference/plant-part-profiles.json'
    return json.loads(path.read_text(encoding='utf-8'))


def references(species, part, indication=''):
    part = normalize_part(part)
    records = [row for row in catalog() if row['part'] == part]
    matches = [row for row in records if species and species_key(row['species']) == species_key(species)]
    result = {
        'species': species,
        'part': part,
        'images': [row['image'] for row in matches],
        'studies': [row['study'] for row in matches],
        'example_species': list(dict.fromkeys(row['species'] for row in records)),
    }
    if species:
        def phrase(value):
            return '"' + value.replace('"', '').strip() + '"'

        organ_query = ' OR '.join(phrase(term) for term in PART_TERMS.get(part, (part,)))
        query = f'{phrase(species)} AND ({organ_query})'
        result['search'] = {
            'images': 'https://commons.wikimedia.org/w/index.php?' + urlencode({
                'title': 'Special:MediaSearch', 'type': 'image', 'search': f'{species} {part}',
            }),
            'research': 'https://pubmed.ncbi.nlm.nih.gov/?' + urlencode({'term': query}),
        }
        if indication.strip():
            result['search']['indication'] = 'https://pubmed.ncbi.nlm.nih.gov/?' + urlencode({
                'term': query + ' AND ' + phrase(indication),
            })
    return result
