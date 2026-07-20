"""Foundry entitlements — the reusable Nyquest Pro access layer.

The session cookie (minted by the shared SSO handoff) already carries the user's
Nyquest `tier`. This module turns a session into the canonical entitlement shape
and makes the access decision. A `MOCK_PRO_USER` flag supports local dev, and the
real Nyquest subscription API plugs in at `_live_entitlement()`.
"""
import os

REQUIRED_PLAN = os.environ.get("FOUNDRY_REQUIRED_PLAN", "pro").lower()
GATE_ENABLED = os.environ.get("FOUNDRY_GATE_ENABLED", "true").lower() != "false"
MOCK_PRO_USER = os.environ.get("MOCK_PRO_USER", "false").lower() == "true"
PRO_PLANS = ["pro", "team", "teams", "enterprise"]
ALL_PACKAGES = ["builder", "marketplace", "prompter", "memorymaker", "rag",
                "trustgate", "spendguard", "modelbench", "eval"]


def _plan_ok(plan):
    plan = (plan or "free").lower()
    if REQUIRED_PLAN == "pro":
        return plan in PRO_PLANS
    return plan == REQUIRED_PLAN or plan in PRO_PLANS


def entitlement_from_session(session: dict | None) -> dict:
    """Canonical entitlement shape. `session` is the decoded zb_session claims."""
    if not session:
        if MOCK_PRO_USER:
            return _mock()
        return {"user_id": None, "email": None, "plan": None, "subscription_status": "unauthenticated",
                "foundry_access": False, "allowed_packages": [], "reason": "not_authenticated"}
    plan = str(session.get("tier") or "free").lower()
    # Nyquest tiers are the source of truth; an active paid tier == active subscription.
    status = "active" if plan in PRO_PLANS else "inactive"
    ok = _plan_ok(plan) and status == "active"
    return {
        "user_id": session.get("sub"), "email": session.get("email"), "name": session.get("name"),
        "plan": plan, "subscription_status": status,
        "foundry_access": ok, "allowed_packages": ALL_PACKAGES if ok else [],
        "reason": None if ok else ("plan_required" if status == "active" else "subscription_inactive"),
    }


def _mock():
    return {"user_id": "mock_pro_user", "email": "dev@zoidlab.ai", "name": "Dev (mock Pro)",
            "plan": "pro", "subscription_status": "active", "foundry_access": True,
            "allowed_packages": ALL_PACKAGES, "reason": None, "mock": True}


def _mock_session():
    """Session-like claims for local dev when MOCK_PRO_USER=true."""
    return {"sub": "mock_pro_user", "email": "dev@zoidlab.ai", "name": "Dev (mock Pro)", "tier": "pro"}


def _live_entitlement(token: str) -> dict:
    """PLUG-IN POINT for the real Nyquest subscription API. When Nyquest exposes a
    subscription/entitlement endpoint, call it here with the user's token and map the
    response onto the canonical shape above. Not used while the session tier is the
    source of truth."""
    raise NotImplementedError("Wire the real Nyquest subscription API here.")


def has_access(session: dict | None) -> bool:
    if not GATE_ENABLED:
        return True
    return entitlement_from_session(session).get("foundry_access", False)
