# investment_advisor.py
from __future__ import annotations

from typing import Any, List, Sequence

# Keep the same exported function name for backward compatibility with app.py callers.
# The function now accepts either normalized dataclass models or plain dicts and returns List[str].

def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Internal: safe attribute/key access for model or dict."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def _num(value: Any, default: float = 0.0) -> float:
    """Internal: coerce to non-negative float."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(default)
    return float(v) if v >= 0 else 0.0

# PUBLIC_INTERFACE
def suggest_investments(
    financial_inputs_or_income: Any,
    family_or_profile: Any = None,
    city_or_profile: Any = None,
    savings_goal_amount: Any = None,
    goal_purpose: Any = None,
) -> List[str]:
    """
    Determine concise, deterministic investment advice strings based on inputs.

    Backward compatible call signatures:
    - suggest_investments(income, family_size, city, savings_goal_amount, goal_purpose)
    - suggest_investments(FinancialInputs or dict, UserProfile or dict)

    Parameters:
    - financial_inputs_or_income: FinancialInputs/dataclass/dict with income, goal_amount, goal_purpose;
                                  OR numeric income if using legacy signature.
    - family_or_profile: UserProfile/dataclass/dict (preferred) OR family_size (int) in legacy signature.
    - city_or_profile: Ignored in normalized signature; in legacy, this is the city string.
    - savings_goal_amount: Numeric goal (legacy only; ignored in normalized signature if FinancialInputs provided).
    - goal_purpose: String (legacy only; ignored in normalized signature if FinancialInputs provided).

    Returns:
    - List[str]: concise, rule-based advice strings. No side effects or external services.
    """
    # Normalize inputs
    # Case A: New signature with models/dicts
    if not isinstance(financial_inputs_or_income, (int, float)):
        fin = financial_inputs_or_income
        prof = family_or_profile
        income = _num(_get(fin, "income", 0.0))
        goal_amount = _num(_get(fin, "goal_amount", _get(fin, "savings_goal", 0.0)), 0.0)
        purpose_raw = _get(fin, "goal_purpose", "") or ""
        family_size = int(_num(_get(prof, "family_size", 1), 1))
        city = str(_get(prof, "city", "") or "")
    else:
        # Case B: Legacy signature with primitives
        income = _num(financial_inputs_or_income, 0.0)
        family_size = 1
        try:
            family_size = max(1, int(float(family_or_profile)))
        except Exception:
            family_size = 1
        city = str(city_or_profile or "")
        goal_amount = _num(savings_goal_amount, 0.0)
        purpose_raw = str(goal_purpose or "")

    purpose = purpose_raw.strip().lower()

    advice: List[str] = []

    # Income-based core advice
    if income >= 80000:
        advice.append("Allocate 20%+ to diversified mutual funds or ETFs.")
        advice.append("Use low-cost index funds; evaluate REITs for diversification.")
    elif 40000 <= income < 80000:
        advice.append("Start SIPs in equity mutual funds (about ₹5k–₹10k monthly).")
        advice.append("Build an emergency fund covering 6 months of expenses.")
    else:
        advice.append("Prioritize safe savings like PPF/RD; keep costs low.")
        advice.append("Leverage EPF/NPS or eligible government schemes where applicable.")

    # Family impact
    if family_size >= 4:
        advice.append("Ensure family-wide health cover and term life for dependents.")
    elif family_size == 1 and income >= 60000:
        advice.append("Consider higher equity allocation given lower dependents.")

    # City cost sensitivity (deterministic list; Kolkata/Jharkhand may be moderate)
    high_cost_cities: Sequence[str] = ("Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai")
    if city in high_cost_cities:
        advice.append("Control non-essentials; explore supplemental income streams.")
    elif city in ("Kolkata", "Jharkhand"):
        advice.append("Costs are moderate; keep SIPs disciplined and increase annually.")

    # Purpose-driven guidance
    if purpose in ("retirement", "future", "long-term", "long term"):
        advice.append("Consider NPS and long-term equity funds with glide path.")
    elif purpose in ("vacation", "short-term", "short term", "wedding", "car"):
        advice.append("Prefer short-duration debt funds/FDs to preserve capital.")
    elif purpose in ("education", "child", "kids"):
        advice.append("Blend equity index funds with debt; review horizon and risk.")

    # Goal amount thresholding
    if goal_amount >= 500000:
        advice.append("Use a diversified equity-debt mix and automate SIPs towards the target.")
    elif 100000 <= goal_amount < 500000:
        advice.append("Set a monthly SIP target and review quarterly against the goal.")

    # Universal hygiene
    advice.append("Review your budget quarterly and track spending consistently.")

    # Deduplicate while preserving order for conciseness
    seen = set()
    concise = []
    for tip in advice:
        if tip not in seen:
            seen.add(tip)
            concise.append(tip)

    return concise
