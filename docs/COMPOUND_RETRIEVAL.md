# Process 3: complete source lookup, rather than five demonstration compounds

BIO-GEN now searches the entire installed LOTUS release for the confirmed scientific plant name. It returns all matching species records from that release, with no fixed five-result limit. This remains documented-source coverage, not a laboratory determination of every compound present in a specimen.

## Installed source

- LOTUS 2026-04-13: https://doi.org/10.5281/zenodo.19360665
- Release metadata declares CC BY 4.0; this release's attribution is retained even though earlier initiative pages describe CC0 data.
- 674,454 referenced occurrence triples, 227,298 structure entries and 37,469 organism-name labels. These include non-plant organisms; they are not 37,469 medicinal plants.
- Both downloaded CSV files were checked against release sizes and MD5 checksums.
- Core occurrence rows and all available structural metadata are indexed locally, so normal queries work offline.

## Matching and evidence

Names are normalized for case and whitespace and matched exactly. Same-taxon identifiers in the release connect labels. An explicit Ocimum tenuiflorum / Ocimum sanctum synonym pair is supported. There is no silent fuzzy-name or genus-wide expansion.

This LOTUS export does not annotate plant parts. Its compounds are therefore explicitly marked **part unverified**. A separate, independently curated catalog provides part-specific associations when available. The user may include the species-level records (default) or restrict to records supported for the selected part.

A missing plant or part produces an evidence gap, not an assertion of chemical absence. Repeated queries against the same snapshot and species should return the same results. Chemical composition is not inferred from image health, symptoms, or an LLM.

## Structures and selection

All retrieved structures are retained. Canonical isomeric SMILES deduplication merges citations rather than discarding duplicate evidence. Physicochemical descriptors come from the original IMPPAT script, with RDKit QED and molecular drawings added.

Property filters are **off by default**. Enabling them flags which compounds meet the chosen limits; it does not delete the other source records. Search and 24-card pages affect only the current display. CSV and JSON cover the full results; source records without usable structures remain explicitly unanalysed.

## Verified examples in this snapshot

- Ocimum tenuiflorum: 106 valid unique structures; five with curated leaf support.
- Azadirachta indica: 449 valid unique structures; part unverified in this release.
- Mentha spicata: 195 valid unique structures; part unverified.
- Mangifera indica: 770 valid unique structures plus one retained unanalysed source record.

Counts describe the installed sources and structure normalization; they are not experimental counts for the user's plant. See full-compound-validation.json and full-compound-interface-verification.json.

## Reproduce

From the project folder:

    .venv/Scripts/python.exe scripts/download_lotus.py
    .venv/Scripts/python.exe scripts/index_lotus.py

Stop the application before rebuilding its database. Keep the release attribution, citation and original source references. Add independently sourced part-specific records using scripts/import_compounds.py.

## COCONUT fallback for missing species

When LOTUS has no species records and species-only results are enabled, BIO-GEN queries the public COCONUT organism-search API, reconciles its paginated candidates, and checks the exact species in each compound page's structured taxonomic annotations. It never accepts a prefix match such as Citrus limonia as Citrus limon. The documented hybrid spellings Citrus limon / Citrus × limon are treated as equivalent. References link to the database association rather than falsely assigning every compound-level article to this plant.

Verified results are cached locally for repeatable offline use. The external source can return overlapping pages whose unique identifiers do not reach its advertised total. Such results are explicitly marked incomplete and retain a coverage warning; they are not presented as all compounds. The Refresh external source control retries the provider. Source failures, strict plant-part restrictions and complete zero-result searches have distinct messages.

COCONUT API: https://coconut.naturalproducts.net/api-documentation . Source code: https://github.com/Steinbeck-Lab/coconut . Lemon taxonomic reference: https://powo.science.kew.org/taxon/urn%3Alsid%3Aipni.org%3Anames%3A60454758-2 .
