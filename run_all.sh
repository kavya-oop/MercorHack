#!/usr/bin/env bash
# Runs tests -> generate -> AI -> check -> evaluate -> stress test.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
$PY -m pytest -q
$PY -m epr.generator --n 20
$PY -u -m epr.ai_runner || echo "AI run incomplete (use manual mode if no API access)"
$PY -m epr.checker --source gemini
$PY -m epr.evaluate --source gemini > /dev/null
$PY -m epr.inject_errors
$PY -m epr.checker --source injected
$PY -m epr.evaluate --source injected > /dev/null
echo "Done. See data/results/*/evaluation.md ; demo: .venv/bin/streamlit run app.py"
