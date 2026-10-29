from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_db, get_session, get_state
from backend.app.schemas.charts import (
    ChartPanelOut,
    ChartsConfigOut,
    ChartsPanelsResponse,
    ChartsResponse,
    ChartsTolerancePctOut,
    ChartTraceOut,
    PanelTraceOut,
)
from backend.app.services.charts import ChartMaterialNotFoundError, ChartService


router = APIRouter(prefix="/charts", tags=["charts"])
service = ChartService()


@router.get("", response_model=ChartsResponse)
def charts(
    material_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    smooth: bool = True,
    con=Depends(get_db),
    state=Depends(get_state),
    _session=Depends(get_session),
):
    try:
        traces = service.series(
            con,
            subsidiary_id=state.subsidiary_id,
            material_id=int(material_id),
            date_from=date_from,
            date_to=date_to,
            smooth=bool(smooth),
        )
    except ChartMaterialNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return ChartsResponse(
        material_id=int(material_id),
        date_from=date_from,
        date_to=date_to,
        traces=[ChartTraceOut(name=trace.name, x=trace.x, y=trace.y) for trace in traces],
    )


@router.get("/config", response_model=ChartsConfigOut)
def charts_config(con=Depends(get_db), state=Depends(get_state), _session=Depends(get_session)):
    tolerance, properties = service.config(con, subsidiary_id=state.subsidiary_id)
    return ChartsConfigOut(
        tolerance_pct=ChartsTolerancePctOut(
            warn_pct=(float(tolerance["warn_pct"]) if tolerance.get("warn_pct") is not None else None),
            alarm_pct=(float(tolerance["alarm_pct"]) if tolerance.get("alarm_pct") is not None else None),
        ),
        fixed_properties=properties,
        defaults={"smooth": True, "avg": True, "tolerances": True},
    )


@router.get("/panels", response_model=ChartsPanelsResponse)
def charts_panels(
    material_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    smooth: bool = True,
    avg: bool = True,
    tolerances: bool = True,
    con=Depends(get_db),
    state=Depends(get_state),
    _session=Depends(get_session),
):
    try:
        panels = service.panels(
            con,
            subsidiary_id=state.subsidiary_id,
            material_id=int(material_id),
            date_from=date_from,
            date_to=date_to,
            smooth=bool(smooth),
            include_average=bool(avg),
            include_tolerances=bool(tolerances),
        )
    except ChartMaterialNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return ChartsPanelsResponse(
        material_id=int(material_id),
        date_from=date_from,
        date_to=date_to,
        panels=[
            ChartPanelOut(
                property_id=panel.property_id,
                title=panel.title,
                unit=panel.unit,
                traces=[
                    PanelTraceOut(name=trace.name, x=trace.x, y=trace.y, kind=trace.kind)
                    for trace in panel.traces
                ],
            )
            for panel in panels
        ],
    )
