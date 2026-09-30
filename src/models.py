from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


class BlueprintError(ValueError):
    """Raised on an invalid standard or manifest."""


# ---- Standard -------------------------------------------------------------
@dataclass
class Zone:
    name: str
    order: int
    kind: str
    description: str
    table_prefix: Optional[str] = None
    format: Optional[str] = None
    path: Optional[str] = None


@dataclass
class Standard:
    zones: dict[str, Zone]
    naming_pattern: str
    naming_max_length: int
    schema_per_zone: bool
    audit_columns: dict[str, list[dict]]
    preferred_partition_columns: list[str]
    max_partition_columns: int
    table_properties: dict[str, str]
    allowed_types: set[str]

    @property
    def name_re(self) -> re.Pattern:
        return re.compile(self.naming_pattern)

    def table_zones(self) -> list[Zone]:
        return sorted(
            (z for z in self.zones.values() if z.kind == "table"),
            key=lambda z: z.order,
        )

    def reserved_columns(self, layer: str) -> set[str]:
        return {c["name"] for c in self.audit_columns.get(layer, [])}


def load_standard(path: str | Path) -> Standard:
    data = _read_yaml(path, "standard")
    zones = {}
    for zname, z in data.get("zones", {}).items():
        zones[zname] = Zone(
            name=zname, order=z["order"], kind=z["kind"],
            description=z.get("description", ""),
            table_prefix=z.get("table_prefix"),
            format=z.get("format"), path=z.get("path"),
        )
    if not zones:
        raise BlueprintError("Standard must define at least one zone.")

    naming = data.get("naming", {})
    part = data.get("partitioning", {})
    return Standard(
        zones=zones,
        naming_pattern=naming.get("pattern", "^[a-z][a-z0-9_]*$"),
        naming_max_length=naming.get("max_length", 100),
        schema_per_zone=naming.get("schema_per_zone", True),
        audit_columns=data.get("audit_columns", {}),
        preferred_partition_columns=part.get("preferred_columns", []),
        max_partition_columns=part.get("max_partition_columns", 2),
        table_properties=data.get("table_properties", {}),
        allowed_types=set(data.get("allowed_types", [])),
    )


# ---- Manifest -------------------------------------------------------------
@dataclass
class Column:
    name: str
    type: str
    nullable: bool = True


@dataclass
class Table:
    name: str
    layers: list[str]
    business_keys: list[str]
    columns: list[Column]
    partition_by: list[str] = field(default_factory=list)


@dataclass
class Domain:
    name: str
    tables: list[Table]


@dataclass
class Manifest:
    lakehouse: str
    domains: list[Domain]

    def all_tables(self):
        for d in self.domains:
            for t in d.tables:
                yield d, t


def load_manifest(path: str | Path) -> Manifest:
    data = _read_yaml(path, "manifest")
    if "lakehouse" not in data:
        raise BlueprintError("Manifest must define a 'lakehouse'.")
    if not data.get("domains"):
        raise BlueprintError("Manifest must define at least one domain.")

    domains = []
    for d in data["domains"]:
        tables = []
        for t in d.get("tables", []):
            cols = [Column(**c) for c in t.get("columns", [])]
            tables.append(Table(
                name=t["name"], layers=t.get("layers", []),
                business_keys=t.get("business_keys", []),
                columns=cols, partition_by=t.get("partition_by", []),
            ))
        domains.append(Domain(name=d["name"], tables=tables))
    return Manifest(lakehouse=data["lakehouse"], domains=domains)


def _read_yaml(path: str | Path, label: str) -> dict:
    path = Path(path)
    if not path.exists():
        raise BlueprintError(f"{label} file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise BlueprintError(f"{label} top-level YAML must be a mapping.")
    return data
