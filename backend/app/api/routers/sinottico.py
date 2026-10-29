from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.app.api.deps import get_db, get_session, get_write_db, require_permission
from backend.app.schemas.sinottico import (
    EmailDraftOut,
    FinalizeQueueResponse,
    QueueRowOut,
    SinotticoRowOut,
)
from backend.app.services.notifications import EmailTemplateNotFoundError
from backend.app.services.sinottico import EmptyQueueError, SinotticoService


router = APIRouter(prefix="/sinottico", tags=["sinottico"])
service = SinotticoService()
can_send = Depends(require_permission("can_send_outlook"))


@router.get("", response_model=list[SinotticoRowOut])
def dashboard(con=Depends(get_db), _session=Depends(get_session)):
    return [SinotticoRowOut(**row.__dict__) for row in service.dashboard(con)]


@router.get("/queue", response_model=list[QueueRowOut], dependencies=[can_send])
def queue(con=Depends(get_db), session=Depends(get_session)):
    return [
        QueueRowOut(
            item_id=row.item_id,
            machine_code=row.machine_code,
            material_code=row.material_code,
            description=row.description,
            lastrina_code=row.lastrina_code,
            last_request_date=row.last_request_date,
        )
        for row in service.queue(con, user_id=int(session.user_id))
    ]


@router.post("/queue/items/{item_id}", status_code=204, dependencies=[can_send])
def queue_add(item_id: int, con=Depends(get_write_db), session=Depends(get_session)):
    service.enqueue(con, user_id=int(session.user_id), item_id=int(item_id))


@router.delete("/queue/items/{item_id}", status_code=204, dependencies=[can_send])
def queue_remove(item_id: int, con=Depends(get_write_db), session=Depends(get_session)):
    service.remove(con, user_id=int(session.user_id), item_id=int(item_id))


@router.delete("/queue", status_code=204, dependencies=[can_send])
def queue_clear(con=Depends(get_write_db), session=Depends(get_session)):
    service.clear(con, user_id=int(session.user_id))


def _draft(con, *, session, locale: str):
    try:
        draft = service.email_preview(
            con,
            user_id=int(session.user_id),
            username=str(session.username),
            locale=str(locale or "it_IT"),
        )
    except EmptyQueueError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Queue is empty")
    except EmailTemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email template not found")
    return draft


@router.post("/queue/email-preview", response_model=EmailDraftOut, dependencies=[can_send])
def email_preview(locale: str = "it_IT", con=Depends(get_db), session=Depends(get_session)):
    return EmailDraftOut(**_draft(con, session=session, locale=locale).__dict__)


@router.post("/queue/email.eml", dependencies=[can_send])
def email_eml(locale: str = "it_IT", con=Depends(get_db), session=Depends(get_session)):
    content = service.notifications.as_eml(_draft(con, session=session, locale=locale))
    filename = f"pe3-sample-request-{date.today().isoformat()}.eml"
    return Response(
        content=content,
        media_type="message/rfc822",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/queue/finalize", response_model=FinalizeQueueResponse, dependencies=[can_send])
def finalize(locale: str = "it_IT", con=Depends(get_write_db), session=Depends(get_session)):
    try:
        logged, created = service.finalize(
            con,
            user_id=int(session.user_id),
            username=str(session.username),
            locale=str(locale or "it_IT"),
        )
    except EmailTemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email template not found")
    return FinalizeQueueResponse(sample_requests_logged=logged, tests_created=created)
