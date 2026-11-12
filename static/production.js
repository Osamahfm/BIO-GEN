const productionNumber = new Intl.NumberFormat(undefined, { maximumFractionDigits: 6 });
const signedProductionNumber = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 6, signDisplay: 'exceptZero',
});

function productionBottleneck(row, assumptions) {
  const supply = assumptions.precursor_capacity;
  const baselineCapacity = assumptions.reaction_capacity ?? assumptions.egs1_capacity;
  if (![supply, baselineCapacity, row.capacity_factor, row.flux].every(Number.isFinite)) return '';
  const capacity = baselineCapacity * row.capacity_factor;
  const tolerance = 1e-6;
  if (Math.abs(row.flux - Math.min(supply, capacity)) > tolerance) return '';
  const format = value => productionNumber.format(value);
  if (capacity === 0) return 'Modeled reaction blocked';
  const explanation = Math.abs(supply - capacity) <= tolerance
    ? 'Both limits are equal'
    : capacity < supply ? 'Reaction capacity limits output' : 'Precursor supply limits output';
  return `${explanation} · capacity ${format(capacity)}, supply ${format(supply)}`;
}

function productionInsights(result) {
  const { scenarios, assumptions } = result;
  const baseline = scenarios.find(row => row.name === 'Baseline');
  const increased = scenarios.find(row => row.capacity_factor > 1);
  if (!baseline || !increased) return '';
  const [low, high] = assumptions.precursor_sensitivity_range;
  const comparisons = [
    ['Low', low, baseline.low_supply_flux, increased.low_supply_flux],
    ['Default', assumptions.precursor_capacity, baseline.flux, increased.flux],
    ['High', high, baseline.high_supply_flux, increased.high_supply_flux],
  ];
  if (comparisons.some(([, supply, from, to]) => ![supply, from, to].every(Number.isFinite))) return '';
  const gains = comparisons.map(([, , from, to]) => to - from);
  const tolerance = 1e-6;
  const format = value => productionNumber.format(value);
  const sensitive = Math.max(...gains) - Math.min(...gains) > tolerance;
  const noGain = comparisons.filter((_, index) => Math.abs(gains[index]) <= tolerance);
  let interpretation = 'The modeled change is similar at all three tested supply levels.';
  if (gains.every(gain => Math.abs(gain) <= tolerance)) {
    interpretation = 'Increasing reaction capacity gives no modeled gain at the tested supply levels.';
  } else if (sensitive && noGain.length && gains.some(gain => gain > tolerance)) {
    const levels = noGain.map(([, supply]) => format(supply)).join(' and ');
    interpretation = `The modeled gain disappears at the tested supply of ${levels}.`;
  } else if (sensitive) {
    interpretation = 'The size of the modeled gain changes with precursor supply.';
  }
  const nextCheck = sensitive
    ? 'Check precursor availability before assuming that increasing reaction capacity will improve production.'
    : 'Check the pathway capacity assumptions against measurements for the selected compound and plant part.';
  return `<section class="production-insights" aria-labelledby="productionInsightsTitle">
    <h5 id="productionInsightsTitle">What limits production?</h5>
    <p><strong>${interpretation}</strong> Compare baseline with increased reaction capacity at the same supply.</p>
    <dl class="production-insight-points">${comparisons.map(([label, supply, from, to], index) =>
      `<div><dt>${label} supply · ${format(supply)}</dt><dd>${format(from)} → ${format(to)} <small>(${signedProductionNumber.format(Number(gains[index].toFixed(6)))})</small></dd></div>`).join('')}</dl>
    <p class="production-insight-note"><strong>Next check</strong> ${nextCheck} The model uses illustrative limits and reports flux in arbitrary units.</p>
  </section>`;
}

function productionResults(result) {
  const { scenarios, assumptions, limitations } = result;
  const format = value => productionNumber.format(value);
  const axisMax = Math.max(1, ...scenarios.flatMap(row => [row.flux, row.low_supply_flux, row.high_supply_flux]));
  const ticks = [0, 1, 2, 3, 4].map(index => index * axisMax / 4);
  const [lowSupply, highSupply] = assumptions.precursor_sensitivity_range;
  const [summary, ...details] = limitations;
  const rows = scenarios.map(row => {
    const low = Math.min(row.low_supply_flux, row.high_supply_flux);
    const high = Math.max(row.low_supply_flux, row.high_supply_flux);
    const range = low === high ? format(low) : `${format(low)}–${format(high)}`;
    const delta = signedProductionNumber.format(row.delta);
    const bottleneck = productionBottleneck(row, assumptions);
    return `<div class="flux-row">
      <div class="flux-scenario"><h5>${esc(row.name)}</h5><span>Supply range <b>${range}</b></span>${bottleneck ? `<small class="production-bottleneck">${esc(bottleneck)}</small>` : ''}</div>
      <div class="flux-plot" aria-hidden="true" style="--flux:${100 * row.flux / axisMax}%;--low:${100 * low / axisMax}%;--spread:${100 * (high - low) / axisMax}%">
        <div class="flux-track"><span></span></div>
        <div class="flux-range"><span></span></div>
      </div>
      <div class="flux-value"><strong>${format(row.flux)}</strong>
        <small>${row.name === 'Baseline' ? 'Reference' : `${delta} vs baseline`}</small>
      </div>
    </div>`;
  }).join('');

  return `<section class="production-results" aria-labelledby="productionResultsTitle">
    <div class="flux-heading">
      <div><p>${esc(result.target.name)} · ${esc(result.gene)}</p>
      <h4 id="productionResultsTitle">Modeled production by scenario</h4></div>
      <span>${esc(result.method)}</span>
    </div>
    <div class="flux-body">
      ${productionInsights(result)}
      <p class="flux-units">Maximum eugenol output in ${esc(result.unit)}</p>
      <ul class="flux-legend" aria-label="Chart legend">
        <li><i class="flux-legend-bar" aria-hidden="true"></i>Nominal supply (${format(assumptions.precursor_capacity)})</li>
        <li><i class="flux-legend-range" aria-hidden="true"></i>Supply sensitivity (${format(lowSupply)}–${format(highSupply)})</li>
      </ul>
      ${rows}
      <div class="flux-axis" aria-hidden="true">
        <div>${ticks.map(tick => `<span>${format(tick)}</span>`).join('')}</div>
      </div>
      <div class="flux-limitations">
        <h5>How to interpret these results</h5>
        <p>${esc(summary)}</p>
        <details><summary>See model limitations</summary>
          <ul>${details.map(text => `<li>${esc(text)}</li>`).join('')}</ul>
        </details>
      </div>
      <div class="flux-provenance">
        <span>Input revision ${result.input_revision}</span>
        <code>${esc(result.model_id)}</code>
        <a href="${esc(safeURL(result.engine_url))}" target="_blank" rel="noopener">COBRApy ${esc(result.engine_version)} ↗</a>
        <span>${esc(result.solver)} solver</span>
      </div>
    </div>
  </section>`;
}

async function renderProduction() {
  const panel = $('processPanel');
  const caseId = current.id;
  const revision = current.revision;
  panel.innerHTML = '<p class="subtle" role="status">Checking pathway coverage…</p>';
  const stillViewing = () => step === 4 && current?.id === caseId && current?.revision === revision;
  let config;
  try {
    config = await api(`/api/cases/${caseId}/production`);
  } catch (error) {
    if (stillViewing()) panel.textContent = error.message;
    return;
  }
  if (!stillViewing()) return;

  const result = current.production;
  const assumptions = config.assumptions;
  const [lowSupply, highSupply] = assumptions.precursor_sensitivity_range;
  panel.innerHTML = `<div class="section-top"><div>
    <div class="panel-kicker">PROCESS 04 · C3 → C4</div>
    <h3>Genetic & production simulation</h3>
    <p class="subtle">Compare how hypothetical changes in enzyme capacity affect compound production in a pathway model.</p>
    </div><span class="pill">${result ? 'C4 SAVED' : config.available ? 'READY' : 'HELD'}</span></div>
    ${config.reason ? `<div class="notice">${esc(config.reason)}</div>` : ''}
    ${config.target ? `<div class="notice green"><strong>${esc(config.target.name)}</strong> from Process 3 ·
      ${esc(config.species)} leaves · ${esc(config.gene)} (eugenol synthase)
      ${config.target.source_url ? ` · <a href="${esc(safeURL(config.target.source_url))}" target="_blank" rel="noopener">Compound evidence ↗</a>` : ''}</div>
    <details class="notice"><summary>Model assumptions and evidence</summary>
      <p>COBRApy maximizes eugenol output in a reduced steady-state pathway. The baseline enzyme capacity is ${assumptions.egs1_capacity}.
      Knockdown halves this capacity, knockout removes the reaction, and the overexpression proxy doubles the capacity.
      Precursor supply is ${assumptions.precursor_capacity} by default, with sensitivity checks at ${lowSupply} and ${highSupply}.</p>
      ${config.sources.map(ref => `<p><a href="${esc(safeURL(ref.url))}" target="_blank" rel="noopener">${esc(ref.label)} ↗</a></p>`).join('')}
    </details>` : ''}
    ${config.available ? `<button class="button primary" id="runProduction">${result ? 'Rerun' : 'Run'} production scenarios →</button>` : ''}
    ${result ? productionResults(result) : ''}`;
  bind('runProduction', async () => {
    const button = $('runProduction');
    button.disabled = true;
    try {
      await mutate('production', {});
      toast('Production scenarios saved as C4.');
    } finally {
      button.disabled = false;
    }
  });
}
