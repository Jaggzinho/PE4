from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import (
    get_db,
    get_serialized_db,
    get_session,
    get_state,
    get_write_db,
    require_permission,
)
from backend.app.schemas.lots import LotDetailsOut, LotsPageOut, LotsRowOut, LotUpsertRequest
from backend.app.services.lots import LotNotFoundError, LotsService, MaterialNotVisibleError


router = APIRouter(prefix="/lots", tags=["lots"])
service = LotsService()


def _row_out(row) -> LotsRowOut:
    return LotsRowOut(
        test_id=row.test_id,
        material_id=row.material_id,
        material_code=row.material_code,
        material_desc=row.material_desc,
        lastrina_code=row.lastrina_code,
        request_date=row.request_date,
        prod_date=row.prod_date,
        analysis_date=row.analysis_date,
        iso_code=row.iso_code,
        iso_desc=row.iso_desc,
        iso_lot=row.iso_lot,
        pol_code=row.pol_code,
        pol_desc=row.pol_desc,
        pol_lot=row.pol_lot,
        cat_code=row.cat_code,
        cat_desc=row.cat_desc,
        cat_lot=row.cat_lot,
        add1_code=row.add1_code,
        add1_desc=row.add1_desc,
        add1_lot=row.add1_lot,
        add2_code=row.add2_code,
        add2_desc=row.add2_desc,
        add2_lot=row.add2_lot,
        durezza=row.durezza,
        carico_rottura=row.carico_rottura,
        allungamento=row.allungamento,
        lacerazione_ba=row.lacerazione_ba,
        lacerazione_ca=row.lacerazione_ca,
        abrasione=row.abrasione,
        resistivita_superficiale=row.resistivita_superficiale,
    )


@router.get("", response_model=LotsPageOut)
def lots(
    limit: int = Query(default=2000, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    material_id: int | None = Query(default=None, ge=1),
    test_id: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None, max_length=200),
    date_field: Literal["request_date", "prod_date", "analysis_date"] = "request_date",
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: Literal["all", "completed", "awaiting_production", "awaiting_analysis"] = Query(default="all", alias="status"),
    sort_by: Literal[
        "latest", "request_date", "prod_date", "analysis_date", "material", "lastrina",
        "iso", "pol", "cat", "add1", "add2", "durezza", "carico_rottura",
        "allungamento", "lacerazione_ba", "lacerazione_ca", "abrasione",
        "resistivita_superficiale",
    ] = "latest",
    sort_dir: Literal["asc", "desc"] = "desc",
    iso: str | None = Query(default=None, max_length=100),
    pol: str | None = Query(default=None, max_length=100),
    cat: str | None = Query(default=None, max_length=100),
    add1: str | None = Query(default=None, max_length=100),
    add2: str | None = Query(default=None, max_length=100),
    qc_field: Literal[
        "durezza", "carico_rottura", "allungamento", "lacerazione_ba",
        "lacerazione_ca", "abrasione", "resistivita_superficiale",
    ] | None = None,
    qc_min: float | None = None,
    qc_max: float | None = None,
    include_deleted: bool = False,
    con=Depends(get_db),
    state=Depends(get_state),
    _session=Depends(get_session),
):
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date_from must be on or before date_to")
    if qc_min is not None and qc_max is not None and qc_min > qc_max:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="qc_min must be less than or equal to qc_max")
    rows, total = service.list(
        con,
        subsidiary_id=state.subsidiary_id,
        limit=int(limit),
        offset=int(offset),
        include_deleted=bool(include_deleted),
        material_id=material_id,
        test_id=test_id,
        query=q,
        date_field=date_field,
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        component_filters={"iso": iso or "", "pol": pol or "", "cat": cat or "", "add1": add1 or "", "add2": add2 or ""},
        qc_field=qc_field,
        qc_min=qc_min,
        qc_max=qc_max,
    )
    return LotsPageOut(
        items=[_row_out(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + len(rows) < total,
    )


@router.get("/{test_id}", response_model=LotDetailsOut)
def lot_details(
    test_id: int,
    con=Depends(get_db),
    state=Depends(get_state),
    _session=Depends(get_session),
):
    try:
        details = service.get(con, subsidiary_id=state.subsidiary_id, test_id=int(test_id))
    except LotNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return LotDetailsOut(**details)


@router.post(
    "",
    response_model=LotDetailsOut,
    dependencies=[Depends(require_permission("can_edit_tests"))],
)
def lot_create(
    payload: LotUpsertRequest,
    con=Depends(get_write_db),
    state=Depends(get_state),
    session=Depends(get_session),
):
    try:
        details = service.create(
            con,
            subsidiary_id=state.subsidiary_id,
            payload=payload,
            created_by=int(session.user_id),
        )
    except MaterialNotVisibleError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Material not visible")
    return LotDetailsOut(**details)


@router.put(
    "/{test_id}",
    response_model=LotDetailsOut,
    dependencies=[Depends(require_permission("can_edit_tests"))],
)
def lot_update(
    test_id: int,
    payload: LotUpsertRequest,
    con=Depends(get_write_db),
    state=Depends(get_state),
    _session=Depends(get_session),
):
    try:
        details = service.update(
            con,
            subsidiary_id=state.subsidiary_id,
            test_id=int(test_id),
            payload=payload,
        )
    except MaterialNotVisibleError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Material not visible")
    except LotNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return LotDetailsOut(**details)


@router.delete(
    "/{test_id}",
    status_code=204,
    dependencies=[Depends(require_permission("can_edit_tests"))],
)
def lot_delete(
    test_id: int,
    con=Depends(get_serialized_db),
    state=Depends(get_state),
    _session=Depends(get_session),
):
    try:
        service.delete(con, subsidiary_id=state.subsidiary_id, test_id=int(test_id))
    except LotNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
