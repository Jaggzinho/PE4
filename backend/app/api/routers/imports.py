from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.app.api.deps import (
    get_job_manager,
    get_session,
    get_state,
    get_write_db,
    require_permission,
)
from backend.app.jobs.manager import JobManager, JobNotFoundError, JobSnapshot
from backend.app.schemas.imports import ImportResultOut, ImportXlsmResponse
from backend.app.schemas.jobs import JobCreatedOut, JobOut
from backend.app.services.imports import ImportService, InvalidWorkbookError, WorkbookTooLargeError
from pe3_qc_app.importer.import_service import import_workbook


router = APIRouter(tags=["imports"])
service = ImportService()
can_import = Depends(require_permission("can_edit_master"))


@router.post(
    "/import",
    deprecated=True,
    responses={
        status.HTTP_501_NOT_IMPLEMENTED: {
            "description": "This pre-v1 import endpoint is no longer implemented",
        }
    },
)
def import_excel_compatibility(_session=Depends(get_session)):
    """Preserve the authenticated response exposed by the original web API."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented in v1")


def _save_upload(file: UploadFile, *, max_bytes: int) -> Path:
    try:
        return service.save_validated_upload(file, max_bytes=max_bytes)
    except WorkbookTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc))
    except InvalidWorkbookError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _job_out(snapshot: JobSnapshot) -> JobOut:
    return JobOut(
        job_id=snapshot.job_id,
        kind=snapshot.kind,
        status=snapshot.status,
        progress=snapshot.progress,
        messages=snapshot.messages,
        result=ImportResultOut(**snapshot.result) if snapshot.result is not None else None,
        error=snapshot.error,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


@router.post(
    "/imports",
    response_model=JobCreatedOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[can_import],
)
def submit_import(
    file: UploadFile = File(...),
    state=Depends(get_state),
    jobs: JobManager = Depends(get_job_manager),
    session=Depends(get_session),
):
    path = _save_upload(file, max_bytes=state.max_import_bytes)
    try:
        snapshot = jobs.submit_import(owner_id=int(session.user_id), workbook_path=path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return JobCreatedOut(job_id=snapshot.job_id, status=snapshot.status)


@router.get("/jobs/{job_id}", response_model=JobOut)
def job_status(
    job_id: str,
    jobs: JobManager = Depends(get_job_manager),
    session=Depends(get_session),
):
    try:
        snapshot = jobs.get(
            job_id,
            owner_id=int(session.user_id),
            can_manage=bool(session.permissions.get("can_manage_users")),
        )
    except JobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _job_out(snapshot)


@router.get("/jobs", response_model=list[JobOut])
def recent_jobs(
    limit: int = 20,
    jobs: JobManager = Depends(get_job_manager),
    session=Depends(get_session),
):
    if not 1 <= limit <= 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
    return [
        _job_out(snapshot)
        for snapshot in jobs.list_recent(
            owner_id=int(session.user_id),
            can_manage=bool(session.permissions.get("can_manage_users")),
            limit=limit,
        )
    ]


@router.post(
    "/import/xlsm",
    response_model=ImportXlsmResponse,
    dependencies=[can_import],
)
def import_xlsm_compatibility(
    file: UploadFile = File(...),
    con=Depends(get_write_db),
    state=Depends(get_state),
    _session=Depends(get_session),
):
    path = _save_upload(file, max_bytes=state.max_import_bytes)
    messages: list[str] = []
    try:
        result = import_workbook(con, path, lambda message: messages.append(str(message)))
        return ImportXlsmResponse(
            logs=messages,
            result=ImportResultOut(
                materials=int(result.materials),
                properties=int(result.properties),
                tests=int(result.tests),
                measurements=int(result.measurements),
                sinottico_items=int(result.sinottico_items),
                component_types=int(result.component_types),
                components=int(result.components),
                material_component_defaults=int(result.material_component_defaults),
            ),
        )
    finally:
        path.unlink(missing_ok=True)
