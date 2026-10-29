from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutlookPayload:
    to_list: str
    cc_list: str
    subject: str
    body: str
    is_html: bool


def create_or_send_email(*, payload: OutlookPayload, mode: str) -> None:
    """
    mode: "draft" or "send"
    """
    try:
        import win32com.client  # type: ignore
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("pywin32/win32com is not available.") from e

    # Prefer DispatchEx to avoid attaching to an existing automation session.
    try:
        app = win32com.client.DispatchEx("Outlook.Application")
    except Exception:
        app = win32com.client.Dispatch("Outlook.Application")

    create_item = getattr(app, "CreateItem", None)
    if create_item is None:
        raise RuntimeError(
            "Outlook COM automation is not available. "
            "If you are using the 'New Outlook' app, switch to 'Classic Outlook' (COM is not supported)."
        )

    try:
        mail = create_item(0)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            "Outlook could not create a mail item (COM call failed). "
            "Verify Outlook is installed/configured (Classic Outlook profile) and not blocked by policy."
        ) from e
    mail.To = payload.to_list
    if payload.cc_list:
        mail.CC = payload.cc_list
    mail.Subject = payload.subject
    if payload.is_html:
        mail.HTMLBody = payload.body
    else:
        mail.Body = payload.body

    mu = str(mode).strip().lower()
    if mu == "send":
        mail.Send()
    else:
        # Persist it to Drafts before showing Outlook's compose window.
        mail.Save()
        mail.Display()
