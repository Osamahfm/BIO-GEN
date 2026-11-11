const productionNumber = new Intl.NumberFormat(undefined, { maximumFractionDigits: 6 });
const signedProductionNumber = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 6, signDisplay: 'exceptZero',
});

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
    return `<div class="flux-row">
      <div class="flux-scenario"><h5>${esc(row.name)}</h5><span>Supply range <b>${range}</b></span></div>
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
