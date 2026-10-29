from __future__ import annotations


class PermissionError(Exception):
    pass


def has_permission(session, perm: str) -> bool:
    if session is None:
        return False
    return bool(session.permissions.get(perm))


def require_permission(session, perm: str) -> None:
    if not has_permission(session, perm):
        raise PermissionError(f"Missing permission: {perm}")

