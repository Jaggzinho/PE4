from __future__ import annotations

import unittest

from pe3_qc_app.auth.passwords import hash_password, verify_password


class TestAuthHashing(unittest.TestCase):
    def test_hash_and_verify(self) -> None:
        salt, h = hash_password("secret")
        self.assertTrue(verify_password("secret", salt=salt, expected_hash=h))
        self.assertFalse(verify_password("wrong", salt=salt, expected_hash=h))


if __name__ == "__main__":
    unittest.main()

