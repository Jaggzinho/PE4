from __future__ import annotations

from datetime import date

from pe3_qc_app.db.repos.tests_repo import (
    QC_FIELDS,
    create_test_manual,
    get_test_details,
    hard_delete_test,
    list_lotti_rows,
    update_test_dates,
    update_test_material,
    upsert_component_lot,
    upsert_measurement,
)
from pe3_qc_app.services.material_visibility import get_visible_material_ids


class LotNotFoundError(LookupError):
    pass


class MaterialNotVisibleError(PermissionError):
    pass


class LotsService:
    def _visible_materials(self, con, subsidiary_id: str) -> set[int]:
        return get_visible_material_ids(con, subsidiary_id=subsidiary_id)

    def list(
        self, con, *, subsidiary_id: str, limit: int, offset: int = 0,
        include_deleted: bool, material_id: int | None = None, test_id: int | None = None,
        query: str | None = None, date_field: str = "request_date",
        date_from: date | None = None, date_to: date | None = None,
        status: str = "all", sort_by: str = "latest", sort_dir: str = "desc",
        component_filters: dict[str, str] | None = None,
        qc_field: str | None = None, qc_min: float | None = None, qc_max: float | None = None,
    ):
        visible = self._visible_materials(con, subsidiary_id)
        return list_lotti_rows(
            con, limit=limit, offset=offset, include_deleted=include_deleted,
            material_id=material_id, test_id=test_id, query=query,
            date_field=date_field, date_from=date_from, date_to=date_to,
            status=status, sort_by=sort_by, sort_dir=sort_dir,
            component_filters=component_filters, qc_field=qc_field, qc_min=qc_min, qc_max=qc_max,
            return_total=True,
            visible_material_ids=visible,
        )

    def get(self, con, *, subsidiary_id: str, test_id: int) -> dict:
        try:
            details = get_test_details(con, test_id=test_id)
        except Exception as exc:
            raise LotNotFoundError from exc
        if int(details["material_id"]) not in self._visible_materials(con, subsidiary_id):
            raise LotNotFoundError
        return details

    def create(self, con, *, subsidiary_id: str, payload, created_by: int) -> dict:
        if int(payload.material_id) not in self._visible_materials(con, subsidiary_id):
            raise MaterialNotVisibleError
        test_id = create_test_manual(
            con,
            material_id=int(payload.material_id),
            request_date=payload.request_date,
            prod_date=payload.prod_date,
            analysis_date=payload.analysis_date,
            created_by=created_by,
        )
        self._save_extras(con, test_id=int(test_id), payload=payload)
        return get_test_details(con, test_id=int(test_id))

    def update(self, con, *, subsidiary_id: str, test_id: int, payload) -> dict:
        visible = self._visible_materials(con, subsidiary_id)
        if int(payload.material_id) not in visible:
            raise MaterialNotVisibleError
        try:
            existing = get_test_details(con, test_id=test_id)
        except Exception as exc:
            raise LotNotFoundError from exc
        if int(existing["material_id"]) not in visible:
            raise LotNotFoundError

        if int(existing["material_id"]) != int(payload.material_id):
            update_test_material(con, test_id=test_id, material_id=int(payload.material_id))
        if (
            existing.get("request_date") != payload.request_date
            or existing.get("prod_date") != payload.prod_date
            or existing.get("analysis_date") != payload.analysis_date
        ):
            update_test_dates(
                con,
                test_id=test_id,
                request_date=payload.request_date,
                prod_date=payload.prod_date,
                analysis_date=payload.analysis_date,
            )
        self._save_extras(con, test_id=test_id, payload=payload)
        return get_test_details(con, test_id=test_id)

    def delete(self, con, *, subsidiary_id: str, test_id: int) -> None:
        self.get(con, subsidiary_id=subsidiary_id, test_id=test_id)
        hard_delete_test(con, test_id=test_id)

    def _save_extras(self, con, *, test_id: int, payload) -> None:
        components = payload.components or {}
        for type_name in ("ISO", "POL", "CAT", "ADD1", "ADD2", "ADD3", "ADD4", "EXT"):
            component = components.get(type_name) or None
            upsert_component_lot(
                con,
                test_id=test_id,
                type_name=type_name,
                component_code=(component.code if component else None),
                component_desc=(component.desc if component else None),
                lot_code=(component.lot if component else None),
            )

        qc = payload.qc or {}
        for field, label in QC_FIELDS:
            upsert_measurement(con, test_id=test_id, property_name=label, value=qc.get(field))
