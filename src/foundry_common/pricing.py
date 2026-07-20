"""Model price table — published list prices, USD per 1M tokens.

These are provider LIST prices (input / output) as of mid-2025. They are used to
compute cost from real token counts — the arithmetic is exact, but the prices are a
static snapshot and can lag the providers' actual billing. Treated as reference data,
not a live billing feed. `cost_usd(...)` is deterministic.
"""

# name -> (input $/1M, output $/1M, provider, tier)
PRICES = {
    "gpt-4o":              (2.50, 10.00, "openai", "frontier"),
    "gpt-4o-mini":         (0.15,  0.60, "openai", "efficient"),
    "gpt-4.1":             (2.00,  8.00, "openai", "frontier"),
    "gpt-4.1-mini":        (0.40,  1.60, "openai", "efficient"),
    "o3-mini":             (1.10,  4.40, "openai", "reasoning"),
    "claude-sonnet-4.5":   (3.00, 15.00, "anthropic", "frontier"),
    "claude-3.5-sonnet":   (3.00, 15.00, "anthropic", "frontier"),
    "claude-3.5-haiku":    (0.80,  4.00, "anthropic", "efficient"),
    "claude-3-opus":       (15.00, 75.00, "anthropic", "frontier"),
    "gemini-2.5-flash":    (0.075, 0.30, "google", "efficient"),
    "gemini-2.5-pro":      (1.25, 10.00, "google", "frontier"),
    "gemini-1.5-flash":    (0.075, 0.30, "google", "efficient"),
    "deepseek-chat":       (0.27,  1.10, "deepseek", "efficient"),
    "deepseek-reasoner":   (0.55,  2.19, "deepseek", "reasoning"),
    "llama-3.3-70b":       (0.59,  0.79, "meta", "open"),
    "mistral-large":       (2.00,  6.00, "mistral", "frontier"),
}

# Snapshot date shown in the UI so nobody mistakes it for live billing.
PRICE_SNAPSHOT = "2025-06"

# Cheaper substitute suggestions for the savings simulator / recommendations.
# Only same-family-or-better-capability swaps that are genuinely cheaper.
CHEAPER_ALT = {
    "gpt-4o": "gpt-4o-mini",
    "gpt-4.1": "gpt-4.1-mini",
    "claude-sonnet-4.5": "claude-3.5-haiku",
    "claude-3.5-sonnet": "claude-3.5-haiku",
    "claude-3-opus": "claude-sonnet-4.5",
    "gemini-2.5-pro": "gemini-2.5-flash",
    "deepseek-reasoner": "deepseek-chat",
    "mistral-large": "gpt-4o-mini",
}


# Relay model IDs are provider-prefixed and versioned (e.g. "anthropic/claude-sonnet-5",
# "openai/gpt-4o-2024-08-06"). Map them onto price-table keys for cost computation.
def resolve(model_id: str) -> str | None:
    """Best-effort map a relay model id onto a price-table key. None if unmatched."""
    if not model_id:
        return None
    m = model_id.lower().split("/")[-1]  # strip provider prefix
    if m in PRICES:
        return m
    # substring / alias matching against known keys and family hints
    aliases = [
        ("claude-sonnet", "claude-sonnet-4.5"), ("claude-3.5-sonnet", "claude-3.5-sonnet"),
        ("claude-3-5-sonnet", "claude-3.5-sonnet"), ("claude-haiku", "claude-3.5-haiku"),
        ("claude-3.5-haiku", "claude-3.5-haiku"), ("claude-3-5-haiku", "claude-3.5-haiku"),
        ("claude-opus", "claude-3-opus"), ("claude-3-opus", "claude-3-opus"),
        ("gpt-4o-mini", "gpt-4o-mini"), ("gpt-4o", "gpt-4o"), ("gpt-4.1-mini", "gpt-4.1-mini"),
        ("gpt-4.1", "gpt-4.1"), ("o3-mini", "o3-mini"),
        ("gemini-2.5-flash", "gemini-2.5-flash"), ("gemini-1.5-flash", "gemini-1.5-flash"),
        ("gemini-2.5-pro", "gemini-2.5-pro"), ("deepseek-reasoner", "deepseek-reasoner"),
        ("deepseek", "deepseek-chat"), ("llama", "llama-3.3-70b"), ("mistral", "mistral-large"),
    ]
    for hint, key in aliases:
        if hint in m:
            return key
    return None


def cost_for(model_id: str, prompt_tokens: int, completion_tokens: int) -> tuple:
    """(cost_usd, price_known) for a relay model id via resolve()."""
    key = resolve(model_id)
    if not key:
        return 0.0, False
    return cost_usd(key, prompt_tokens, completion_tokens), True


def known(model: str) -> bool:
    return model in PRICES


def provider_of(model: str) -> str:
    return PRICES.get(model, (0, 0, "unknown", "unknown"))[2]


def tier_of(model: str) -> str:
    return PRICES.get(model, (0, 0, "unknown", "unknown"))[3]


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Exact cost from token counts and the list price. 0.0 for unknown models."""
    p = PRICES.get(model)
    if not p:
        return 0.0
    inp, out, _, _ = p
    return round((prompt_tokens / 1_000_000) * inp + (completion_tokens / 1_000_000) * out, 6)


def price_row(model: str) -> dict:
    inp, out, prov, tier = PRICES.get(model, (0.0, 0.0, "unknown", "unknown"))
    return {"model": model, "input_per_m": inp, "output_per_m": out,
            "provider": prov, "tier": tier}


def table() -> list:
    return [price_row(m) for m in PRICES]
