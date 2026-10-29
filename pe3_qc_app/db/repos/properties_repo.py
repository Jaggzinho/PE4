from __future__ import annotations

from dataclasses import dataclass

from pe3_qc_app.db.ids import new_id


@dataclass(frozen=True)
class Property:
    property_id: int
    name: str
    unit: str | None
    active: bool
    sort_order: int | None


def list_properties(con) -> list[Property]:
    rows = con.execute(
        """
        SELECT property_id, name, unit, active, sort_order
        FROM properties
        ORDER BY COALESCE(sort_order, 9999), name
        """
    ).fetchall()
    return [
        Property(
            property_id=int(r[0]),
            name=str(r[1]),
            unit=(str(r[2]) if r[2] is not None else None),
            active=bool(r[3]),
            sort_order=(int(r[4]) if r[4] is not None else None),
        )
        for r in rows
    ]


def upsert_property(
    con,
    *,
    property_id: int | None,
    name: str,
    unit: str | None,
    active: bool,
    sort_order: int | None,
) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Property name is required.")
    if unit is not None:
        unit = unit.strip() or None

    if property_id is None:
        property_id = new_id()
        con.execute(
            """
            INSERT INTO properties(property_id, name, unit, data_type, active, sort_order)
            VALUES (?, ?, ?, 'num', ?, ?)
            """,
            [property_id, name, unit, bool(active), sort_order],
        )
        return int(property_id)

    _update_referenced_property(
        con,
        property_id=int(property_id),
        name=name,
        unit=unit,
        active=bool(active),
        sort_order=sort_order,
    )
    return int(property_id)


def _update_referenced_property(
    con,
    *,
    property_id: int,
    name: str,
    unit: str | None,
    active: bool,
    sort_order: int | None,
) -> None:
    """Update a property despite DuckDB's referenced-row UPDATE limitation."""
    backups = (
        (
            "_property_measurements_backup",
            "measurements",
            "measurement_id, test_id, property_id, value_num, value_text",
        ),
        (
            "_property_tolerances_backup",
            "tolerances",
            "tolerance_id, material_id, property_id, warn_low, warn_high, alarm_low, alarm_high, updated_at",
        ),
        (
            "_property_rating_weights_backup",
            "rating_property_weights",
            "property_id, weight",
        ),
        (
            "_property_rating_rules_backup",
            "rating_property_rules",
            "property_id, rule_json",
        ),
    )

    for backup, table, columns in backups:
        con.execute(f"DROP TABLE IF EXISTS {backup}")
        con.execute(
            f"CREATE TEMP TABLE {backup} AS SELECT {columns} FROM {table} WHERE property_id = ?",
            [property_id],
        )

    try:
        for _backup, table, _columns in backups:
            con.execute(f"DELETE FROM {table} WHERE property_id = ?", [property_id])
        con.execute(
            "UPDATE properties SET name=?, unit=?, active=?, sort_order=? WHERE property_id=?",
            [name, unit, active, sort_order, property_id],
        )
        for backup, table, columns in backups:
            con.execute(f"INSERT INTO {table} ({columns}) SELECT {columns} FROM {backup}")
    except BaseException:
        # The endpoint holds the application's serialized write lock. Restore
        # every dependent row if validation or reinsertion fails midway.
        for _backup, table, _columns in backups:
            con.execute(f"DELETE FROM {table} WHERE property_id = ?", [property_id])
        for backup, table, columns in backups:
            con.execute(f"INSERT INTO {table} ({columns}) SELECT {columns} FROM {backup}")
        raise
    finally:
        for backup, _table, _columns in backups:
            con.execute(f"DROP TABLE IF EXISTS {backup}")


def delete_property(con, *, property_id: int) -> None:
    con.execute("DELETE FROM properties WHERE property_id = ?", [int(property_id)])

