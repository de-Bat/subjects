"""Shared FastAPI dependencies: static-bearer auth + DB session.

Single-user auth (spec Section 8): one static bearer token, required on every
/api/* write and on the SSE stream. This is a LAN guard, not multi-tenancy.
Multi-user seam: swap this for real per-user auth later; nothing else changes.
"""
from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


def _check(token: str | None) -> None:
    expected = get_settings().app_token
    if not token or token != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing token")


async def require_token(authorization: str | None = Header(default=None)) -> None:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    _check(token)


async def require_token_query(
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """SSE variant: EventSource can't set headers, so accept ?token= too."""
    resolved = token
    if not resolved and authorization and authorization.lower().startswith("bearer "):
        resolved = authorization[7:]
    _check(resolved)


AuthDep = Depends(require_token)
