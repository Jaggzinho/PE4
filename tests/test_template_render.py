from __future__ import annotations

import unittest

from pe3_qc_app.services.template_render import ALLOWED_EMAIL_TOKENS, render_template


class TestTemplateRender(unittest.TestCase):
    def test_known_tokens_replaced_unknown_preserved(self) -> None:
        tmpl = "A {machine_code} {unknown} {today}"
        out = render_template(
            tmpl,
            values={"machine_code": "M1", "today": "2026-04-17"},
            allowed_keys=ALLOWED_EMAIL_TOKENS,
        )
        self.assertEqual(out, "A M1 {unknown} 2026-04-17")


if __name__ == "__main__":
    unittest.main()

