from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.services.materials import MaterialsService
from backend.app.schemas.materials import MaterialOut
from backend.app.api.deps import get_db, get_session, get_state


router = APIRouter()
service = MaterialsService()


@router.get("/materials", response_model=list[MaterialOut])
def materials(q: str | None = None, con=Depends(get_db), state=Depends(get_state), _session=Depends(get_session)):
    rows = service.search(con, subsidiary_id=state.subsidiary_id, query=q)
    return [
        MaterialOut(
            material_id=row.material_id,
            code=row.code,
            description=row.description,
            lastrina_code=row.lastrina_code,
            lastrina_desc=row.lastrina_desc,
            active=bool(row.active),
            component_defaults=service.component_defaults(con, material_id=int(row.material_id)),
        )
        for row in rows
    ]
