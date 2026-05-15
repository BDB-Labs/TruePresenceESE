"""
Authentication for legacy REST routes mounted under /api (session/create, v1/evaluate, etc.).

When TRUEPRESENCE_LEGACY_REST_TOKEN is unset and the deployment is not production,
these routes stay open for local development and tests.

In production, TRUEPRESENCE_LEGACY_REST_TOKEN must be set; each request must send either:
  - Header X-TruePresence-Service-Token matching that value, or
  - Authorization: Bearer <JWT> from an authenticated dashboard user.

The privacy-preserving SDK endpoint POST /api/v1/truepresence/evaluate-interaction is not gated
by this dependency (it uses separate rate limiting).
"""

from __future__ import annotations

import hmac
import os

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

legacy_rest_bearer = HTTPBearer(auto_error=False)


def _is_production_environment() -> bool:
    env = (
        os.environ.get("TRUEPRESENCE_ENV")
        or os.environ.get("ENVIRONMENT")
        or os.environ.get("APP_ENV")
        or ""
    ).strip().lower()
    if env in {"prod", "production"}:
        return True
    return os.environ.get("TRUEPRESENCE_PRODUCTION", "").strip().lower() in {"1", "true", "yes", "on"}


def legacy_rest_token_configured() -> bool:
    return bool(os.environ.get("TRUEPRESENCE_LEGACY_REST_TOKEN", "").strip())


def require_legacy_rest_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(legacy_rest_bearer),  # noqa: B008
) -> dict | None:
    configured = os.environ.get("TRUEPRESENCE_LEGACY_REST_TOKEN", "").strip()
    if _is_production_environment() and not configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "Production requires TRUEPRESENCE_LEGACY_REST_TOKEN for legacy REST endpoints "
                "(/api/session/create, /api/v1/evaluate, session cluster/reset). "
                "Send X-TruePresence-Service-Token or Authorization: Bearer (JWT). "
                "Browser integrations should prefer POST /api/v1/truepresence/evaluate-interaction."
            ),
        )
    if not configured:
        return None

    service = request.headers.get("X-TruePresence-Service-Token", "")
    if service and hmac.compare_digest(service, configured):
        return {"auth": "service"}

    if credentials:
        from truepresence.api.auth import get_current_user

        return {"auth": "jwt", "user": get_current_user(credentials)}

    raise HTTPException(
        status_code=401,
        detail=(
            "Legacy REST requires X-TruePresence-Service-Token or Authorization: Bearer (JWT). "
            "Set TRUEPRESENCE_LEGACY_REST_TOKEN on the server and send the token from trusted clients."
        ),
    )
