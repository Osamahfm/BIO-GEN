"""Evidence-linked, steady-state production scenarios for supported C3 compounds."""

from importlib.util import find_spec

from .part_profiles import normalize_part, species_key

SPECIES = 'Ocimum tenuiflorum'
PART = 'leaves'
MODEL_ID = 'tulsi-leaf-eugenol-v1'
EUGENOL_SMILES = 'C=CCc1ccc(O)c(OC)c1'
ENGINE_URL = 'https://github.com/opencobra/cobrapy'
SOURCES = (
    {'label': 'Holy basil leaf EGS1 expression and essential oil study',
     'url': 'https://ojs.kmutnb.ac.th/index.php/ijst/article/view/6797'},
    {'label': 'Functional characterization of eugenol synthase across Ocimum species',
     'url': 'https://pubmed.ncbi.nlm.nih.gov/27519164/'},
)
ASSUMPTIONS = {
    'precursor_capacity': 10.0,
    'precursor_sensitivity_range': [4.0, 12.0],
    'egs1_capacity': 6.0,
    'knockdown_capacity_factor': 0.5,
    'overexpression_capacity_factor': 2.0,
}
LIMITATIONS = [
    'This reduced pathway uses assumed capacities in arbitrary flux units. '
    'It does not estimate measured yield or a quantitative gene-expression response.',
    'The precursor pool abstracts upstream reactions and cofactors. The model omits other '
    'synthases, competing sinks, transport, growth and cultivar effects.',
    'A model knockout removes the only modeled eugenol-producing reaction. '
    'A zero model flux does not establish absence of eugenol in the plant.',
]


def options(case):
    profile = case['profile']
    discovery = case.get('discovery')
    target = None
    if not discovery:
        reason = 'Complete Process 3 to link a compound to this simulation.'
    elif (profile.get('species_confirmed') is False
          or species_key(profile.get('scientific_name', '')) != species_key(SPECIES)
          or normalize_part(profile.get('plant_part', '')) != PART):
        reason = 'The current model covers eugenol in Tulsi leaves. This species or part needs its own pathway model.'
    else:
        target = next((row for row in discovery.get('compounds', [])
                       if row.get('smiles') == EUGENOL_SMILES
                       and row.get('part_status') == 'reported_for_selected_part'), None)
        reason = None if target else 'Process 3 needs a eugenol structure with Tulsi leaf evidence to run this model.'

    ready = find_spec('cobra') is not None
    if target and not ready:
        reason = 'Install the COBRApy dependency to run Process 4.'
    return {
        'available': target is not None and ready, 'reason': reason,
        'model_id': MODEL_ID, 'species': SPECIES, 'plant_part': PART, 'gene': 'EGS1',
        'target': ({key: target.get(key) for key in ('name', 'smiles', 'part_status', 'source_url', 'references')}
                   if target else None),
        'sources': list(SOURCES), 'assumptions': ASSUMPTIONS,
    }


def simulate(case, configuration):
    from cobra import Metabolite, Model, Reaction, __version__

    model = Model(MODEL_ID)
    model.solver = 'glpk'
    precursor = Metabolite('activated_coniferyl_pool', compartment='c')
    eugenol = Metabolite('eugenol', compartment='c')
    supply = Reaction('PRECURSOR_SUPPLY', lower_bound=0, upper_bound=ASSUMPTIONS['precursor_capacity'])
    supply.add_metabolites({precursor: 1})
    synthase = Reaction('EUGENOL_SYNTHASE', lower_bound=0, upper_bound=ASSUMPTIONS['egs1_capacity'])
    synthase.add_metabolites({precursor: -1, eugenol: 1})
    synthase.gene_reaction_rule = 'EGS1'
    sink = Reaction('EUGENOL_OUTPUT', lower_bound=0, upper_bound=1000)
    sink.add_metabolites({eugenol: -1})
    model.add_reactions([supply, synthase, sink])
    model.objective = sink
    scenarios = []
    for name, factor in (
        ('Baseline', 1.0),
        ('EGS1 knockdown', ASSUMPTIONS['knockdown_capacity_factor']),
        ('EGS1 knockout', 0.0),
        ('EGS1 overexpression proxy', ASSUMPTIONS['overexpression_capacity_factor']),
    ):
        with model:
            if factor == 0:
                model.genes.get_by_id('EGS1').knock_out()
            else:
                synthase.upper_bound = ASSUMPTIONS['egs1_capacity'] * factor
            values = []
            for capacity in [ASSUMPTIONS['precursor_capacity'], *ASSUMPTIONS['precursor_sensitivity_range']]:
                supply.upper_bound = capacity
                solution = model.optimize()
                if solution.status != 'optimal':
                    raise RuntimeError(f'Flux balance solver returned {solution.status}.')
                values.append(round(float(solution.objective_value), 6))
            flux, low, high = values
            scenarios.append({'name': name, 'capacity_factor': factor, 'flux': flux,
                              'low_supply_flux': low, 'high_supply_flux': high,
                              'delta': round(flux - (scenarios[0]['flux'] if scenarios else flux), 6)})
    return dict(configuration, engine='COBRApy', engine_version=__version__, engine_url=ENGINE_URL,
                solver='GLPK', method='Flux balance analysis', objective='Maximize EUGENOL_OUTPUT',
                unit='arbitrary flux units', input_revision=case['revision'], scenarios=scenarios,
                limitations=LIMITATIONS, recommendations_held=True)
