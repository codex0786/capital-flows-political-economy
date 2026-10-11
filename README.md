# Capital in Motion

**Live app:** https://codex0786.github.io/capital-flows-political-economy/ (redeployed automatically when `results/prototype/index.html` changes on `main`)

**Political Policies, Institutional Stability and International Capital Flows Across Advanced and Emerging Economies, 2015–2026**

A pre-registered, reproducible panel study of how national elections, institutional quality and global financial conditions relate to cross-border capital flows in 121 economies (annual) and 108 economies (quarterly).

## Headline results

| | Finding | Status |
|---|---|---|
| H1a/H1b | No change in gross inflows/outflows in the pre-election window (−0.14 and +0.40 pp of GDP; Holm p = 1.00) | Confirmatory |
| H2, H6, H3, H5 | No institutional, AE/EMDE, asset-class or VIX-moderation effects survive adjustment | Confirmatory |
| Post-election | Gross inflows and outflows both fall ≈1.4 pp in the two quarters after elections; sign robust, significance fragile | Secondary |
| Election quarter, EMDEs | −2.15 pp (WCB p = 0.001; placebo p < 0.001; robust to country × season FE); the prior political-stability moderation does **not** replicate | **Post-hoc** |

Full write-up: [`report/final_report.md`](report/final_report.md). Protocol: [`report/research_protocol.md`](report/research_protocol.md) (git tag `protocol-v1.0`). Changes after results: [`report/protocol_changelog.md`](report/protocol_changelog.md).

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run_pipeline.sh
```

Downloads are skipped when a raw file already exists (the archive in `data/raw/` is immutable). The raw archive (~400 MB) is not committed; `data/raw/source_register_log.csv` records every file's URL, timestamp and SHA-256 hash. A full rerun from the archive on 2026-10-11 reproduced every results table and processed dataset byte-for-byte.

## Layout

```
config/          analysis_config.yaml (sample, windows, inference), variable_dictionary.csv
data/raw/        immutable source archive (git-ignored) + source_register_log.csv
data/interim/    tidy per-source tables (git-ignored, rebuilt)
data/processed/  annual_country_panel.parquet, quarterly_country_panel.parquet, political_events.csv,
                 policy_events.csv, country_metadata.csv, data_quality_report.csv, source_register.csv
src/ingest/      one module per source family (IMF BOP/WEO/RSUI, World Bank, V-Dem, IDEA, Wikipedia, WUI, GPR, BIS, FRED)
src/cleaning/    raw -> interim parsers
src/features/    elections.py (triangulated coding), build_panels.py, documentation.py
src/validation/  data_quality.py
src/econometrics/ models.py, run_analysis.py (protocol v1.0), robustness.py, posthoc_alignment.py (post-hoc, labelled)
src/visualisation/ figures.py (Figures 1-10), tables.py
src/literature/  Crossref verification, OpenAlex abstracts, bibliography + evidence matrix builders
tests/           21 pytest checks (keys, BPM6 signs, missingness, panel integrity, election coding, estimators)
results/         tables/, figures/ (PDF/SVG/PNG + source CSV), diagnostics/, logs/
literature/      bibliography.csv (DOI-verified), literature_matrix.csv, sources/
report/          research_protocol.md, protocol_changelog.md, feasibility_report.md, methodology.md,
                 final_report.md, presentation/ (slide source)
```

## Data licences and access

The repository redistributes only derived data. IMF and World Bank data are open; V-Dem (CC BY-SA 4.0) is obtained from the V-Dem Institute's GitHub; Wikipedia content (CC BY-SA 4.0) is used for election dates only; WUI, GPR and KAOPEN are cited as their authors request. See `data/processed/source_register.csv`.

## Software

Python 3.14; pandas, numpy, pyarrow, linearmodels, statsmodels, scipy, matplotlib, pyreadr (V-Dem .RData), xlrd/openpyxl (Excel sources), pypdf (reading the IMF working paper). Exact versions are in `requirements.txt`.
