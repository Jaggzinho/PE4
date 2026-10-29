from __future__ import annotations

from datetime import date
import os

from backend.app.models.domain import EmailDraft
from pe3_qc_app.outlook.outlook_service import OutlookPayload, create_or_send_email
from pe3_qc_app.db.repos.outlook_repo import (
    get_default_template,
    get_template_by_name,
    resolve_emails_for_group,
)
from pe3_qc_app.services.template_render import ALLOWED_EMAIL_TOKENS, render_template
from pe3_qc_app.services.date_format import format_date


class EmailTemplateNotFoundError(LookupError):
    pass


class OutlookDraftError(RuntimeError):
    """The local Outlook client could not open a reviewable draft."""


class NotificationService:
    @staticmethod
    def test_draft() -> EmailDraft:
        return EmailDraft(
            to_list="", cc_list="", subject="PE3 Outlook Test",
            body="This is a test draft created by PE3.", is_html=False,
        )

    def create_outlook_test_draft(self) -> None:
        """Called on a worker thread; COM must be initialized on that thread."""
        if os.getenv("PE3_DISABLE_OUTLOOK_COM", "").strip().lower() in {"1", "true", "yes"}:
            raise OutlookDraftError("Outlook COM is disabled for this test runtime. You can download the .eml draft instead.")
        try:
            import pythoncom  # type: ignore
        except ImportError:
            pythoncom = None
        if pythoncom is not None:
            try:
                pythoncom.CoInitialize()
            except Exception as exc:
                raise OutlookDraftError("Outlook COM could not initialize on this workstation.") from exc
        try:
            draft = self.test_draft()
            create_or_send_email(payload=OutlookPayload(**draft.__dict__), mode="draft")
        except Exception as exc:
            raise OutlookDraftError(
                "Could not create an Outlook draft. Classic Outlook and its configured profile are required. "
                "You can download the .eml draft instead."
            ) from exc
        finally:
            if pythoncom is not None:
                pythoncom.CoUninitialize()

    def queue_preview(self, con, *, queue_rows, locale: str, requester_name: str) -> EmailDraft:
        template = get_template_by_name(con, name=f"Queued Sample Request ({locale})")
        if template is None:
            template = (
                get_template_by_name(con, name=f"Default Sample Request ({locale})")
                or get_default_template(con)
            )
        if template is None:
            raise EmailTemplateNotFoundError

        values = {
            "today": format_date(date.today()),
            "requester_name": requester_name,
            "material_details": self._material_details(queue_rows),
        }
        return EmailDraft(
            to_list="; ".join(resolve_emails_for_group(con, template.to_group)),
            cc_list="; ".join(resolve_emails_for_group(con, template.cc_group)),
            subject=render_template(
                template.subject_tmpl,
                values=values,
                allowed_keys=ALLOWED_EMAIL_TOKENS,
            ),
            body=render_template(
                template.body_tmpl,
                values=values,
                allowed_keys=ALLOWED_EMAIL_TOKENS,
            ),
            is_html=bool(template.is_html),
        )

    @staticmethod
    def as_eml(draft: EmailDraft) -> bytes:
        content_type = "text/html; charset=utf-8" if draft.is_html else "text/plain; charset=utf-8"
        value = (
            "To: " + (draft.to_list or "") + "\r\n"
            + ("Cc: " + draft.cc_list + "\r\n" if draft.cc_list else "")
            + "Subject: " + (draft.subject or "") + "\r\n"
            + "MIME-Version: 1.0\r\n"
            + f"Content-Type: {content_type}\r\n"
            + "Content-Transfer-Encoding: 8bit\r\n\r\n"
            + (draft.body or "")
        )
        return value.encode("utf-8")

    @staticmethod
    def _material_details(queue_rows) -> str:
        lines = []
        for row in queue_rows:
            lines.append(
                f"- MAC: {row.machine_code or ''} | Materiale: {row.material_code or ''} "
                f"| Desc: {row.description or ''} | Lastrina: {row.lastrina_code or ''} "
                f"| Ultima: {format_date(row.last_request_date, empty='—')}"
            )
        return "\n".join(lines).strip()
