from __future__ import annotations

from .models import Manifest, Standard


def validate(manifest: Manifest, standard: Standard) -> list[str]:
    errors: list[str] = []
    name_re = standard.name_re
    table_zone_names = {z.name for z in standard.table_zones()}

    def check_name(label: str, value: str) -> None:
        if not name_re.match(value):
            errors.append(
                f"{label} '{value}' violates naming pattern "
                f"'{standard.naming_pattern}'."
            )
        if len(value) > standard.naming_max_length:
            errors.append(
                f"{label} '{value}' exceeds max length "
                f"{standard.naming_max_length}."
            )

    if not name_re.match(manifest.lakehouse.lower()):
        if not manifest.lakehouse.strip():
            errors.append("Lakehouse name is empty.")

    seen_tables: set[tuple[str, str]] = set()

    for domain, table in manifest.all_tables():
        check_name("Domain", domain.name)
        check_name("Table", table.name)

        key = (domain.name, table.name)
        if key in seen_tables:
            errors.append(f"Duplicate table '{table.name}' in domain "
                          f"'{domain.name}'.")
        seen_tables.add(key)

        col_names = {c.name for c in table.columns}

        if not table.columns:
            errors.append(f"Table '{table.name}': no columns defined.")
        for col in table.columns:
            check_name("Column", col.name)
            base_type = col.type.split("(")[0].strip().lower()
            if base_type not in standard.allowed_types:
                errors.append(
                    f"Table '{table.name}', column '{col.name}': type "
                    f"'{col.type}' not in allowed types."
                )

        if not table.layers:
            errors.append(f"Table '{table.name}': no layers specified.")
        for layer in table.layers:
            if layer not in table_zone_names:
                errors.append(
                    f"Table '{table.name}': layer '{layer}' is not a managed "
                    f"zone ({sorted(table_zone_names)})."
                )

        if not table.business_keys:
            errors.append(f"Table '{table.name}': business_keys required.")
        for bk in table.business_keys:
            if bk not in col_names:
                errors.append(
                    f"Table '{table.name}': business key '{bk}' is not a column."
                )

        for layer in table.layers:
            for reserved in standard.reserved_columns(layer):
                if reserved in col_names:
                    errors.append(
                        f"Table '{table.name}': column '{reserved}' clashes "
                        f"with a reserved audit column for layer '{layer}'."
                    )

        if len(table.partition_by) > standard.max_partition_columns:
            errors.append(
                f"Table '{table.name}': {len(table.partition_by)} partition "
                f"columns exceeds max {standard.max_partition_columns}."
            )
        for p in table.partition_by:
            if p not in col_names:
                errors.append(
                    f"Table '{table.name}': partition column '{p}' is not a column."
                )

    return errors
