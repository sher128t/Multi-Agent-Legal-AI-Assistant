"""Security helpers (stub) for OAuth/RBAC integration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.observability.logging import audit_logger


HTTP_BEARER = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user_id: str
    roles: list[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles


def _parse_token(token: str) -> AuthContext:
    if not token.startswith("demo-"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    parts = token.removeprefix("demo-").split(":")
    user_id = parts[0] or "user"
    roles = parts[1].split(",") if len(parts) > 1 else ["junior", "senior", "compliance"]
    return AuthContext(user_id=user_id, roles=roles)


def get_current_user(credential: Optional[HTTPAuthorizationCredentials] = Depends(HTTP_BEARER)) -> AuthContext:
    if credential is None:
        require_auth = os.getenv("AUTH_OPTIONAL", "false").lower() != "true"
        if require_auth:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth required")
        return AuthContext(user_id="anon", roles=["junior", "senior", "compliance"])

    return _parse_token(credential.credentials)


def require_role(user: AuthContext, roles: Iterable[str]) -> None:
    allowed = set(roles)
    if allowed.isdisjoint(user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role")


def audit_log(event: str, *, user: AuthContext, request_id: str, extra: Optional[dict] = None) -> None:
    payload = {"user_id": user.user_id, "request_id": request_id, **(extra or {})}
    audit_logger().info(event, **payload)


__all__ = ["AuthContext", "get_current_user", "require_role", "audit_log"]

