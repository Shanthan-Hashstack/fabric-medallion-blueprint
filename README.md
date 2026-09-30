# Medallion Architecture Blueprint

Phase 1 of the Fabric accelerator programme. Turns two YAML files — a reusable
**standard** (house rules) and a per-project **manifest** (the tables you want)
— into compliant Fabric Bronze/Silver/Gold notebooks, with naming, audit
columns, partitioning and Delta properties applied automatically.

## Quick start
    pip install jinja2 pyyaml
    python3 provision.py --manifest config/manifest.example.yaml --lint-only
    python3 provision.py --manifest config/manifest.example.yaml --out output

## How it works
- standard/medallion_standard.yaml  — the "how" (set once, reused everywhere)
- config/manifest.example.yaml       — the "what" (edit per project)
- src/validator.py                   — lints the manifest against the standard
- src/provisioner.py                 — generates notebooks from templates
- templates/                         — the reusable code patterns

Onboarding a new table = add a block to the manifest, re-run. The validator
blocks anything that breaks the standard before a single notebook is written.

## Tests
    python3 -m unittest discover -s tests -v
