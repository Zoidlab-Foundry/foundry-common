"""Nyquest relay client — OpenAI-compatible chat gateway at NYQUEST_BASE_URL.

Used by the QA engine to generate a real, grounded answer from retrieved chunks.
Per-request auth uses the signed-in user's OWN relay key (the `rk` claim in the shared
session cookie) so generation bills THEIR Nyquest wallet; falls back to the shared owner
key, and if neither is present the QA engine uses its deterministic assembler instead.

The relay serves chat models but NOT embeddings (verified: /embeddings -> 404), so
semantic retrieval uses a local embedding model, not this client.
"""
import os
import httpx
from contextvars import ContextVar

BASE = os.environ.get("NYQUEST_BASE_URL", "https://api.nyquest.ai/v1").rstrip("/")
KEY = os.environ.get("NYQUEST_API_KEY", "")
DEFAULT_MODEL = os.environ.get("RAG_DEFAULT_MODEL", "anthropic/claude-sonnet-5")
REAL = os.environ.get("ENABLE_REAL_QA", "true").lower() != "false"

_relay_auth: ContextVar = ContextVar("relay_auth", default=None)


def set_relay_auth(value):
    _relay_auth.set(value or None)


def _auth():
    return _relay_auth.get() or KEY


def has_key():
    return bool(_auth())


def billing_mode():
    """Which wallet a generation bills: the user's key, the shared owner key, or none."""
    if _relay_auth.get():
        return "user"
    return "owner" if KEY else "mock"


def available():
    """True when real generation can run (feature on + some key present)."""
    return REAL and has_key()


def _headers():
    return {"Authorization": f"Bearer {_auth()}", "Content-Type": "application/json"}


async def chat(model, messages, temperature=0.2, max_tokens=700):
    """Returns (text, usage_dict). Raises on transport/HTTP error."""
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            f"{BASE}/chat/completions",
            headers=_headers(),
            json={"model": model or DEFAULT_MODEL, "messages": messages,
                  "temperature": temperature, "max_tokens": max_tokens},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"relay {r.status_code}: {r.text[:200]}")
        j = r.json()
        text = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return text, j.get("usage", {}) or {}


_MODELS_CACHE = {"ids": None}
_EXCLUDE = ("image", "audio", "video", "tts", "whisper", "embed", "dall", "veo",
            "imagen", "lyria", "music", "rerank", "moderation", "-realtime")
_FEATURED_HINTS = ["claude-sonnet", "claude-opus", "claude-haiku", "gpt-5", "gpt-4o",
                   "gemini-2.5-pro", "gemini-2.5-flash", "llama-4", "mistral-large"]


async def list_models():
    if _MODELS_CACHE["ids"]:
        return _MODELS_CACHE["ids"]
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{BASE}/models", headers={"Authorization": f"Bearer {KEY}"})
            r.raise_for_status()
            ids = sorted(m.get("id") for m in r.json().get("data", []) if m.get("id"))
            ids = [i for i in ids if not any(x in i.lower() for x in _EXCLUDE)]
            _MODELS_CACHE["ids"] = ids
            return ids
    except Exception:
        return ["auto", "anthropic/claude-sonnet-5", "openai/gpt-5", "google/gemini-2.5-flash"]


async def featured_models():
    ids = await list_models()
    out = ["auto"]
    for hint in _FEATURED_HINTS:
        m = next((i for i in ids if hint in i.lower()), None)
        if m and m not in out:
            out.append(m)
    return out


def cost_estimate(model_id, tokens):
    m = (model_id or "").lower()
    price = 0.005
    if "opus" in m or ("gpt-5" in m and "mini" not in m):
        price = 0.012
    elif "sonnet" in m or "gemini-2.5-pro" in m:
        price = 0.008
    elif "mini" in m or "flash" in m or "haiku" in m or "llama" in m or "mistral" in m:
        price = 0.002
    return round((tokens or 0) / 1000 * price, 5)
