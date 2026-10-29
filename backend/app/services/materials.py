from __future__ import annotations

from pe3_qc_app.db.repos.materials_repo import list_materials
from pe3_qc_app.db.repos.material_components_repo import get_material_component_defaults
from pe3_qc_app.services.material_visibility import get_visible_material_ids


class MaterialsService:
    def search(self, con, *, subsidiary_id: str, query: str | None = None):
        visible = get_visible_material_ids(con, subsidiary_id=subsidiary_id)
        materials = [m for m in list_materials(con) if int(m.material_id) in visible]
        normalized = (query or "").strip().casefold()
        if not normalized:
            return materials
        return [
            material
            for material in materials
            if normalized in material.code.casefold()
            or normalized in (material.description or "").casefold()
            or normalized in (material.lastrina_code or "").casefold()
        ]

    def component_defaults(self, con, *, material_id: int) -> dict[str, dict[str, str | None]]:
        return get_material_component_defaults(con, material_id=material_id)
