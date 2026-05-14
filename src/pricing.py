"""Token pricing and cost calculation for Anthropic models."""

# USD per 1,000,000 tokens (Anthropic published rates, May 2026)
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_create": 18.75,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_create": 3.75,
    },
    "claude-sonnet-4-5": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_create": 3.75,
    },
    "claude-haiku-4-5": {
        "input": 0.25,
        "output": 1.25,
        "cache_read": 0.025,
        "cache_create": 0.3125,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.25,
        "output": 1.25,
        "cache_read": 0.025,
        "cache_create": 0.3125,
    },
}

_DEFAULT_PRICING = {
    "input": 3.00,
    "output": 15.00,
    "cache_read": 0.30,
    "cache_create": 3.75,
}


def _get_rates(model: str) -> dict[str, float]:
    """Return pricing rates for model, falling back to sonnet defaults."""
    # Exact match first
    if model in PRICING:
        return PRICING[model]
    # Prefix match (e.g. "claude-sonnet-4-6-20250514" → sonnet-4-6)
    for key in PRICING:
        if model.startswith(key):
            return PRICING[key]
    return _DEFAULT_PRICING


def calculate_cost(usage: dict, model: str) -> float:
    """Calculate USD cost for a single API response usage dict."""
    rates = _get_rates(model)
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_create = usage.get("cache_creation_input_tokens", 0)

    cost = (
        input_tokens * rates["input"] / 1_000_000
        + output_tokens * rates["output"] / 1_000_000
        + cache_read * rates["cache_read"] / 1_000_000
        + cache_create * rates["cache_create"] / 1_000_000
    )
    return cost


def format_cost(usd: float) -> str:
    """Format USD cost as string."""
    if usd < 0.01:
        return f"${usd:.4f}"
    return f"${usd:,.2f}"
