from __future__ import annotations

from email import policy
from email.parser import BytesParser
import threading
from types import SimpleNamespace
import sys

from backend.app.services import notifications
from pe3_qc_app.outlook.outlook_service import OutlookPayload, create_or_send_email
from tests.test_web_api import _auth, _client


def test_outlook_settings_authorization_and_eml_contents(tmp_path):
    client = _client(tmp_path)
    viewer = client.post("/api/auth/login", json={"username": "viewer", "password": "pw"}).json()
    viewer_headers = {"Authorization": f"Bearer {viewer['access_token']}"}
    for path, method in (("/api/settings/outlook/test-draft", "post"), ("/api/settings/outlook/test-draft.eml", "get")):
        assert getattr(client, method)(path).status_code == 401
        assert getattr(client, method)(path, headers=viewer_headers).status_code == 403

    headers = {"Authorization": f"Bearer {_auth(client)}"}
    response = client.get("/api/settings/outlook/test-draft.eml", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("message/rfc822")
    draft = BytesParser(policy=policy.default).parsebytes(response.content)
    assert draft["To"] is not None and str(draft["To"]) == ""
    assert draft["Cc"] is None
    assert draft["Subject"] == "PE3 Outlook Test"
    assert draft.get_content().strip() == "This is a test draft created by PE3."


def test_outlook_draft_runs_in_worker_and_reports_recoverable_failure(tmp_path, monkeypatch):
    client = _client(tmp_path)
    headers = {"Authorization": f"Bearer {_auth(client)}"}
    calls = []
    # The service imports pythoncom locally, as required for the worker thread.
    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        CoInitialize=lambda: calls.append("init"),
        CoUninitialize=lambda: calls.append("uninit"),
    ))
    worker_ids = []

    def create(*, payload, mode):
        worker_ids.append(threading.get_ident())
        assert payload.to_list == payload.cc_list == ""
        assert payload.subject == "PE3 Outlook Test"
        assert payload.body == "This is a test draft created by PE3."
        assert payload.is_html is False and mode == "draft"

    monkeypatch.setattr(notifications, "create_or_send_email", create)
    response = client.post("/api/settings/outlook/test-draft", headers=headers)
    assert response.status_code == 200
    assert worker_ids and worker_ids[0] != threading.get_ident()
    assert calls == ["init", "uninit"]

    def unavailable(**_kwargs):
        raise RuntimeError("Outlook is not installed")

    monkeypatch.setattr(notifications, "create_or_send_email", unavailable)
    response = client.post("/api/settings/outlook/test-draft", headers=headers)
    assert response.status_code == 503
    assert response.json()["code"] == "service_unavailable"
    assert ".eml" in response.json()["message"]
    assert client.get("/api/settings/outlook/test-draft.eml", headers=headers).status_code == 200
    assert calls == ["init", "uninit", "init", "uninit"]


def test_outlook_transport_saves_draft_without_sending(monkeypatch):
    events = []
    mail = SimpleNamespace(
        To=None, Subject=None, Body=None,
        Save=lambda: events.append("save"),
        Display=lambda: events.append("display"),
        Send=lambda: events.append("send"),
    )
    client = SimpleNamespace(DispatchEx=lambda _name: SimpleNamespace(CreateItem=lambda _kind: mail))
    monkeypatch.setitem(sys.modules, "win32com", SimpleNamespace(client=client))
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    create_or_send_email(
        payload=OutlookPayload("", "", "PE3 Outlook Test", "This is a test draft created by PE3.", False),
        mode="draft",
    )
    assert events == ["save", "display"]
    assert (mail.To, mail.Subject, mail.Body) == ("", "PE3 Outlook Test", "This is a test draft created by PE3.")
