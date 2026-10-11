#!/usr/bin/env bash
# Reproduce the full study. Raw downloads are skipped when files already exist in data/raw
# (the archive is immutable); delete a file to force a fresh download of that source.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python

echo "== 1. Ingest (skips existing raw files)"
$PY -m src.ingest.imf_bop A Q
$PY -c "from src.ingest.imf_bop import download_official_oi; download_official_oi('Q')"
$PY -m src.ingest.macro_sources weo wb fred unc bis idea vdem
$PY -m src.ingest.wikipedia_calendar

echo "== 2. Parse raw -> interim (one process per step; V-Dem needs ~2 GB RAM)"
for s in meta bop_a bop_q weo wdi wgi vdem idea wui gpr rsui kaopen policy fred; do
  $PY -m src.cleaning.parse_sources "$s"
done

echo "== 3. Build analytical datasets and documentation"
$PY -m src.features.build_panels
$PY -m src.features.documentation

echo "== 4. Validate"
$PY -m src.validation.data_quality
$PY -m pytest -q tests

echo "== 5. Pre-specified analysis (protocol v1.0) and robustness"
$PY -m src.econometrics.run_analysis
$PY -m src.econometrics.robustness

echo "== 6. Post-hoc (exploratory) alignment analysis"
$PY -m src.econometrics.posthoc_alignment
$PY -c "from src.econometrics.posthoc_alignment import placebo_k0, seasonality_check; placebo_k0(); seasonality_check()"

echo "== 7. Literature, tables, figures"
$PY -m src.literature.build_literature
$PY -m src.visualisation.tables
$PY -m src.visualisation.figures


echo "== 8. Interactive prototype"
$PY -m src.forecast.country_model
$PY -c "from src.forecast.country_model import rolling_point_backtest; rolling_point_backtest()"
$PY -m src.forecast.risk
$PY -m src.forecast.vulnerability
# report/preregistration_2026_* is frozen (git tag prereg-2026-elections); do not regenerate
$PY -m src.prototype.export_bundle
$PY -m src.prototype.build_app
echo "done"
