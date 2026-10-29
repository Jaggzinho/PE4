from __future__ import annotations

import unittest

from pe3_qc_app.auth.rbac import has_permission, require_permission, PermissionError
from pe3_qc_app.core.context import Session


class TestRBAC(unittest.TestCase):
    def test_require_permission(self) -> None:
        s = Session(user_id=1, username="u", role_name="r", permissions={"can_edit_master": True})
        self.assertTrue(has_permission(s, "can_edit_master"))
        require_permission(s, "can_edit_master")
        with self.assertRaises(PermissionError):
            require_permission(s, "can_manage_users")


if __name__ == "__main__":
    unittest.main()

