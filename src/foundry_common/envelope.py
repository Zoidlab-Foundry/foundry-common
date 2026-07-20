"""Canonical Foundry base package envelope (blueprint §6.2).

Every JSON export across the suite is wrapped in ONE envelope so imports/exports share a
schema and carry an integrity digest, ownership, dependencies, and credential references
(never secret values). The app-specific report is the `payload`.
"""
import json
import hashlib
import datetime

SCHEMA_VERSION = "1.0"


def _digest(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def wrap(foundry_package, resource_type, resource_id, resource_version, payload,
         nyquest_user_id=None, nyquest_org_id=None, dependencies=None, credential_references=None):
    return {
        "schema_version": SCHEMA_VERSION,
        "package_type": "nyquest_foundry_package",
        "foundry_package": foundry_package,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_version": resource_version or "1.0.0",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "created_by": {"nyquest_user_id": nyquest_user_id},
        "organization": {"nyquest_org_id": nyquest_org_id},
        "dependencies": dependencies or [],
        "credential_references": credential_references or [],
        "integrity": {"algorithm": "sha256", "digest": _digest(payload)},
        "payload": payload,
    }


def verify(envelope):
    """Recompute the payload digest and confirm it matches — supports import integrity checks."""
    got = _digest(envelope.get("payload"))
    want = (envelope.get("integrity") or {}).get("digest")
    return got == want
