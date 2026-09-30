#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import Provisioner, load_manifest, load_standard, validate
from src.models import BlueprintError

DEFAULT_STANDARD = "standard/medallion_standard.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provision a compliant medallion lakehouse from a manifest."
    )
    parser.add_argument("--manifest", "-m", required=True)
    parser.add_argument("--standard", "-s", default=DEFAULT_STANDARD)
    parser.add_argument("--out", "-o", default="output")
    parser.add_argument("--templates", "-t", default="templates")
    parser.add_argument("--lint-only", action="store_true")
    args = parser.parse_args()

    try:
        standard = load_standard(args.standard)
        manifest = load_manifest(args.manifest)
    except BlueprintError as exc:
        print(f"LOAD ERROR: {exc}", file=sys.stderr)
        return 2

    errors = validate(manifest, standard)
    if errors:
        print(f"LINT FAILED — {len(errors)} violation(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"Lint passed: manifest '{manifest.lakehouse}' complies with the standard.")
    if args.lint_only:
        return 0

    written = Provisioner(args.templates).generate(manifest, standard, args.out)
    print(f"\nGenerated {len(written)} notebook(s):")
    for p in written:
        print(f"  - {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
