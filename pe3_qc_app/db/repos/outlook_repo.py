from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.services.time_utils import utc_now_naive


@dataclass(frozen=True)
class EmailTemplate:
    template_id: int
    name: str
    to_group: str | None
    cc_group: str | None
    subject_tmpl: str
    body_tmpl: str
    is_html: bool


@dataclass(frozen=True)
class RequestContext:
    item_id: int
    machine_code: str | None
    material_code: str | None
    material_desc: str | None
    lastrina_code: str | None
    last_request_date: date | None


def get_default_template(con) -> EmailTemplate | None:
    row = con.execute(
        """
        SELECT template_id, name, to_group, cc_group, subject_tmpl, body_tmpl, is_html
        FROM email_templates
        WHERE active
        ORDER BY template_id
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    return EmailTemplate(
        template_id=int(row[0]),
        name=str(row[1]),
        to_group=(str(row[2]) if row[2] is not None else None),
        cc_group=(str(row[3]) if row[3] is not None else None),
        subject_tmpl=str(row[4]),
        body_tmpl=str(row[5]),
        is_html=bool(row[6]),
    )


def get_template_by_name(con, *, name: str) -> EmailTemplate | None:
    row = con.execute(
        """
        SELECT template_id, name, to_group, cc_group, subject_tmpl, body_tmpl, is_html
        FROM email_templates
        WHERE active AND name = ?
        LIMIT 1
        """,
        [str(name)],
    ).fetchone()
    if row is None:
        return None
    return EmailTemplate(
        template_id=int(row[0]),
        name=str(row[1]),
        to_group=(str(row[2]) if row[2] is not None else None),
        cc_group=(str(row[3]) if row[3] is not None else None),
        subject_tmpl=str(row[4]),
        body_tmpl=str(row[5]),
        is_html=bool(row[6]),
    )


def resolve_emails_for_group(con, group_name: str | None) -> list[str]:
    if not group_name:
        return []
    rows = con.execute(
        """
        SELECT email
        FROM contacts
        WHERE active AND group_name = ?
        ORDER BY email
        """,
        [group_name],
    ).fetchall()
    out: list[str] = []
    for (email,) in rows:
        if email is None:
            continue
        s = str(email).strip()
        if s:
            out.append(s)
    return out


def load_request_context(con, *, item_id: int) -> RequestContext | None:
    row = con.execute(
        """
        WITH last_req AS (
            SELECT material_id, MAX(request_date) AS last_request_date
            FROM tests
            WHERE deleted_at IS NULL
            GROUP BY material_id
        )
        SELECT
            s.item_id,
            s.machine_code,
            m.code,
            m.description,
            m.lastrina_code,
            lr.last_request_date
        FROM sinottico_items s
        LEFT JOIN materials m ON m.material_id = s.material_id
        LEFT JOIN last_req lr ON lr.material_id = s.material_id
        WHERE s.item_id = ?
        """,
        [item_id],
    ).fetchone()
    if row is None:
        return None
    return RequestContext(
        item_id=int(row[0]),
        machine_code=(str(row[1]) if row[1] is not None else None),
        material_code=(str(row[2]) if row[2] is not None else None),
        material_desc=(str(row[3]) if row[3] is not None else None),
        lastrina_code=(str(row[4]) if row[4] is not None else None),
        last_request_date=row[5],
    )


def log_sample_request(
    con,
    *,
    item_id: int,
    requested_by: int | None,
    outcome: str,
    subject: str,
    to_list: str,
    cc_list: str,
) -> int:
    rid = new_id()
    con.execute(
        """
        INSERT INTO sample_requests(req_id, item_id, requested_at, requested_by, outcome, subject, to_list, cc_list)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [rid, item_id, utc_now_naive(), requested_by, outcome, subject, to_list, cc_list],
    )
    return int(rid)
