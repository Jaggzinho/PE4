from __future__ import annotations

from pe3_qc_app.auth.auth_manager import any_users, authenticate, create_user
from pe3_qc_app.core.context import Session


class SetupDisabledError(RuntimeError):
    pass


class InvalidSetupTokenError(RuntimeError):
    pass


class AlreadySetupError(RuntimeError):
    pass


class PasswordMismatchError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class AuthService:
    def needs_setup(self, con) -> bool:
        return not bool(any_users(con))

    def create_first_admin(
        self,
        con,
        *,
        configured_token: str | None,
        supplied_token: str | None,
        username: str,
        password: str,
        password_confirmation: str,
    ) -> None:
        if configured_token is None:
            raise SetupDisabledError
        if not supplied_token or supplied_token.strip() != configured_token:
            raise InvalidSetupTokenError
        if any_users(con):
            raise AlreadySetupError
        if password != password_confirmation:
            raise PasswordMismatchError
        create_user(con, username=username, password=password, role_name="Admin")

    def login(self, con, *, username: str, password: str) -> Session:
        session = authenticate(con, username=username, password=password)
        if session is None:
            raise InvalidCredentialsError
        return session
