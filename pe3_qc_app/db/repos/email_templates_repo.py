from __future__ import annotations

from dataclasses import dataclass

from pe3_qc_app.db.ids import new_id


@dataclass(frozen=True)
class EmailTemplateRow:
    template_id: int
    name: str
    to_group: str | None
    cc_group: str | None
    subject_tmpl: str
    body_tmpl: str
    is_html: bool
    active: bool


def list_templates(con) -> list[EmailTemplateRow]:
    rows = con.execute(
        """
        SELECT template_id, name, to_group, cc_group, subject_tmpl, body_tmpl, is_html, active
        FROM email_templates
        ORDER BY name
        """
    ).fetchall()
    out: list[EmailTemplateRow] = []
    for r in rows:
        out.append(
            EmailTemplateRow(
                template_id=int(r[0]),
                name=str(r[1]),
                to_group=(str(r[2]) if r[2] is not None else None),
                cc_group=(str(r[3]) if r[3] is not None else None),
                subject_tmpl=str(r[4]),
                body_tmpl=str(r[5]),
                is_html=bool(r[6]),
                active=bool(r[7]),
            )
        )
    return out


def upsert_template(
    con,
    *,
    template_id: int | None,
    name: str,
    to_group: str | None,
    cc_group: str | None,
    subject_tmpl: str,
    body_tmpl: str,
    is_html: bool,
    active: bool,
) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Template name is required.")
    if to_group is not None:
        to_group = to_group.strip() or None
    if cc_group is not None:
        cc_group = cc_group.strip() or None
    if not subject_tmpl.strip():
        raise ValueError("Subject template is required.")
    if not body_tmpl.strip():
        raise ValueError("Body template is required.")

    if template_id is None:
        template_id = new_id()
        con.execute(
            """
            INSERT INTO email_templates(template_id, name, to_group, cc_group, subject_tmpl, body_tmpl, is_html, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [template_id, name, to_group, cc_group, subject_tmpl, body_tmpl, bool(is_html), bool(active)],
        )
        return int(template_id)

    con.execute(
        """
        UPDATE email_templates
        SET name=?, to_group=?, cc_group=?, subject_tmpl=?, body_tmpl=?, is_html=?, active=?
        WHERE template_id=?
        """,
        [name, to_group, cc_group, subject_tmpl, body_tmpl, bool(is_html), bool(active), int(template_id)],
    )
    return int(template_id)


def delete_template(con, *, template_id: int) -> None:
    con.execute("DELETE FROM email_templates WHERE template_id = ?", [int(template_id)])

