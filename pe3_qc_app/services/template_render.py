from __future__ import annotations

import re


_TOKEN_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_template(tmpl: str, *, values: dict[str, str], allowed_keys: set[str]) -> str:
    def repl(m: re.Match) -> str:
        k = str(m.group(1))
        if k not in allowed_keys:
            return m.group(0)
        return str(values.get(k, ""))

    return _TOKEN_RE.sub(repl, str(tmpl))


ALLOWED_EMAIL_TOKENS: set[str] = {
    "machine_code",
    "material_code",
    "material_desc",
    "lastrina_code",
    "last_request_date",
    "today",
    "days_since",
    "requester_name",
    "material_details",
}
