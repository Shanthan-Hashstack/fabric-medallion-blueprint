from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .models import Manifest, Standard

_STRUCT_TYPE_MAP = {
    "string": "StringType()", "int": "IntegerType()", "bigint": "LongType()",
    "smallint": "ShortType()", "double": "DoubleType()", "float": "FloatType()",
    "boolean": "BooleanType()", "date": "DateType()",
    "timestamp": "TimestampType()", "binary": "BinaryType()",
}


def _spark_struct_type(spark_type: str) -> str:
    base = spark_type.split("(")[0].strip().lower()
    if base == "decimal":
        inside = spark_type[spark_type.find("(") + 1: spark_type.find(")")] \
            if "(" in spark_type else "18,2"
        return f"DecimalType({inside})"
    return _STRUCT_TYPE_MAP.get(base, "StringType()")


def _list_literal(items) -> str:
    return "[" + ", ".join(f'"{i}"' for i in items) + "]"


def _make_env(templates_dir: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        undefined=StrictUndefined,
        trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
    )
    env.filters["spark_struct_type"] = _spark_struct_type
    env.filters["list_literal"] = _list_literal
    return env


class Provisioner:
    def __init__(self, templates_dir: str | Path):
        self.env = _make_env(Path(templates_dir))

    def generate(self, manifest: Manifest, standard: Standard,
                 output_dir: str | Path) -> list[Path]:
        output_dir = Path(output_dir)
        (output_dir / "tables").mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        table_zones = standard.table_zones()

        landing = standard.zones.get("landing")
        landing_paths = []
        if landing and landing.path:
            for domain, table in manifest.all_tables():
                landing_paths.append(
                    landing.path.format(domain=domain.name, source=table.name)
                )

        scaffold = self.env.get_template("zone_scaffold.py.j2").render(
            lakehouse=manifest.lakehouse, table_zones=table_zones,
            landing_paths=sorted(set(landing_paths)),
        )
        scaffold_path = output_dir / "00_zone_scaffold.py"
        scaffold_path.write_text(scaffold, encoding="utf-8")
        written.append(scaffold_path)

        tpl = self.env.get_template("create_table.py.j2")
        zones_by_name = {z.name: z for z in table_zones}

        for domain, table in manifest.all_tables():
            for layer_name in table.layers:
                layer = zones_by_name[layer_name]
                code = tpl.render(
                    lakehouse=manifest.lakehouse, table=table, layer=layer,
                    audit_columns=standard.audit_columns.get(layer_name, []),
                    table_properties=standard.table_properties,
                )
                path = output_dir / "tables" / f"{layer.table_prefix}{table.name}.py"
                path.write_text(code, encoding="utf-8")
                written.append(path)

        return written
