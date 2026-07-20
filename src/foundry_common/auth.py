"""Shared ZoidLab session + Foundry Pro access control.

`session()` decodes the shared `zb_session` cookie. `require_pro()` is the FastAPI
dependency every write endpoint uses — it enforces the Nyquest Pro entitlement so
the backend gate matches the frontend gate.
"""
import os
import sys
import jwt
from fastapi import Request, HTTPException
from foundry_common import entitlements

_DEFAULT = "dev-secret-change-me"
SECRET = os.environ.get("BUILDER_SESSION_SECRET", _DEFAULT)

if SECRET == _DEFAULT:
    print("[rag-builder] WARNING: BUILDER_SESSION_SECRET is unset — using an insecure "
          "default. Session cookies are forgeable. Set a real secret before exposing this API.",
          file=sys.stderr)


def session(request: Request):
    tok = request.cookies.get("zb_session")
    if not tok:
        return entitlements._mock_session() if entitlements.MOCK_PRO_USER else None
    try:
        return jwt.decode(tok, SECRET, algorithms=["HS256"])
    except Exception:
        return None


def owner_of(request: Request):
    s = session(request)
    return s.get("sub") if s else None


def relay_key(request: Request):
    """The user's own minted Nyquest relay key (rk claim) — grounded answers bill THEIR
    Nyquest wallet. None falls back to the shared owner key (or deterministic if neither)."""
    s = session(request)
    return s.get("rk") if s else None


def entitlement(request: Request):
    return entitlements.entitlement_from_session(session(request))


def require_pro(request: Request):
    """Enforce Nyquest Pro Foundry access. Returns the owner id (Nyquest user id)."""
    s = session(request)
    ent = entitlements.entitlement_from_session(s)
    if not ent.get("foundry_access"):
        raise HTTPException(status_code=403, detail=ent.get("reason") or "pro_required")
    return ent.get("user_id")
