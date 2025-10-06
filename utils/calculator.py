# utils/calculator.py
"""
Financial calculator utilities.

This module provides:
- load_city_config(city): Load city parameters from config/<city>.json with safe defaults and simple in-memory caching.
- calculate(fin_inputs, profile, city_config): Compute a normalized numeric results dict including totals and breakdown.
- calculate_finance(...) legacy façade: Maintained for backward compatibility in other utilities if any.

All currency formatting is intentionally excluded from this layer; UI/report layers should handle presentation.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

# Module-level cache for city configs
_CONFIG_CACHE: Dict[str, Dict[str, float]] = {}

# Safe defaults used when config is missing/invalid keys
_DEFAULT_CITY_CONFIG: Dict[str, float] = {
    # Baseline monthly rent applied if housing == "Rent"
    "rent_baseline": 8000.0,
    # Multiplier applied to base per-person food cost
    "food_multiplier": 1.0,
    # Baseline transport cost for "Public transport"; own vehicle may scale this up
    "transport_baseline": 2500.0,
    # Multiplier for miscellaneous costs bucket
    "misc_multiplier": 1.1,
}

# Domain constants for unit-safe, simple calculations
_BASE_PER_PERSON_FOOD = 3000.0  # base monthly food cost per person (₹) before city multiplier and preference
_FOOD_PREF_MULTIPLIERS = {
    "Cook at home": 1.0,
    "Order food mostly": 1.4,
}
_TRANSPORT_MODE_MULTIPLIERS = {
    "Public transport": 1.0,
    "Own vehicle": 1.6,  # fuel, parking, maintenance
}
# Family-related misc baseline per member (₹)
_FAMILY_MISC_PER_MEMBER = 1000.0
# Generic misc base (₹) before misc_multiplier
_MISC_BASE = 2000.0


def _clamp_non_negative(value: Any) -> float:
    """Clamp inputs to a non-negative float."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, v)


# PUBLIC_INTERFACE
def load_city_config(base_dir: str, city: str) -> Dict[str, float]:
    """
    Load a city's configuration JSON into a dict of numeric parameters.

    City files are expected at: <base_dir>/config/<city>.json
    Returns safe defaults if file is missing or malformed. Results are cached per city.

    Parameters:
    - base_dir: Project base directory containing the 'config' folder.
    - city: City name used as filename stem (case-sensitive to existing files).

    Returns:
    - dict with keys: rent_baseline, food_multiplier, transport_baseline, misc_multiplier
    """
    # Cache hit
    if city in _CONFIG_CACHE:
        return _CONFIG_CACHE[city]

    cfg_path = os.path.join(base_dir, "config", f"{city.lower()}.json")
    data: Dict[str, Any] = {}
    try:
        if os.path.exists(cfg_path):
            with open(cfg_path, "r") as f:
                data = json.load(f)
        else:
            # Try case-sensitive variant as stored in repo (Kolkata/Jharkhand)
            alt_path = os.path.join(base_dir, "config", f"{city}.json")
            if os.path.exists(alt_path):
                with open(alt_path, "r") as f:
                    data = json.load(f)
    except Exception:
        data = {}

    # Normalize with safe defaults and numeric coercion
    normalized = {
        "rent_baseline": _clamp_non_negative((data or {}).get("rent_baseline", _DEFAULT_CITY_CONFIG["rent_baseline"])),
        "food_multiplier": _clamp_non_negative((data or {}).get("food_multiplier", _DEFAULT_CITY_CONFIG["food_multiplier"])) or 1.0,
        "transport_baseline": _clamp_non_negative((data or {}).get("transport_baseline", _DEFAULT_CITY_CONFIG["transport_baseline"])),
        "misc_multiplier": _clamp_non_negative((data or {}).get("misc_multiplier", _DEFAULT_CITY_CONFIG["misc_multiplier"])) or 1.0,
    }
    _CONFIG_CACHE[city] = normalized
    return normalized


# PUBLIC_INTERFACE
def calculate(fin_inputs: Any, profile: Any, city_config: Dict[str, float]) -> Dict[str, Any]:
    """
    Compute numeric-only totals and breakdown for the given inputs.

    Parameters:
    - fin_inputs: object or dict with fields: income
    - profile: object or dict with fields: city, housing, transport/vehicle, food, family_size
    - city_config: dict from load_city_config with required numeric keys

    Returns:
    - {
        'income': float,
        'total_expenses': float,
        'savings': float,
        'breakdown': {'rent': float, 'food': float, 'transport': float, 'misc': float}
      }
    Notes:
    - All values are numeric; no currency formatting is applied here.
    - Inputs are clamped to non-negative numbers.
    """

    def _get(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    income = _clamp_non_negative(_get(fin_inputs, "income", 0.0))
    city = str(_get(profile, "city", "Kolkata") or "Kolkata")
    housing = str(_get(profile, "housing", "Own") or "Own")
    transport = str(_get(profile, "transport", _get(profile, "vehicle", "Public transport")) or "Public transport")
    food = str(_get(profile, "food", "Cook at home") or "Cook at home")
    family_size_raw = _get(profile, "family_size", 1)
    try:
        family_size = max(1, int(float(family_size_raw)))
    except Exception:
        family_size = 1

    rent_baseline = float(city_config.get("rent_baseline", _DEFAULT_CITY_CONFIG["rent_baseline"]))
    food_mult = float(city_config.get("food_multiplier", _DEFAULT_CITY_CONFIG["food_multiplier"])) or 1.0
    transport_baseline = float(city_config.get("transport_baseline", _DEFAULT_CITY_CONFIG["transport_baseline"]))
    misc_mult = float(city_config.get("misc_multiplier", _DEFAULT_CITY_CONFIG["misc_multiplier"])) or 1.0

    # Compute components
    rent = rent_baseline if housing == "Rent" else 0.0

    food_pref_mult = _FOOD_PREF_MULTIPLIERS.get(food, 1.0)
    food_cost = family_size * _BASE_PER_PERSON_FOOD * food_mult * food_pref_mult

    transport_mode_mult = _TRANSPORT_MODE_MULTIPLIERS.get(transport, 1.0)
    transport_cost = transport_baseline * transport_mode_mult

    family_misc = family_size * _FAMILY_MISC_PER_MEMBER
    misc = (_MISC_BASE * misc_mult) + family_misc

    # Totals
    total_expenses = rent + food_cost + transport_cost + misc
    savings = income - total_expenses

    # Clamp savings to allow negative results if expenses exceed income; UI can message accordingly
    result = {
        "income": float(income),
        "total_expenses": float(total_expenses),
        "savings": float(savings),
        "breakdown": {
            "rent": float(rent),
            "food": float(food_cost),
            "transport": float(transport_cost),
            "misc": float(misc),
        },
    }
    return result


# PUBLIC_INTERFACE
def calculate_finance(income, city, housing, vehicle, food, family_size):
    """
    Legacy façade to maintain backward compatibility with existing app usage.
    Returns a dict similar to the older structure but numeric-only for totals/breakdown.
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    cfg = load_city_config(base_dir, city or "Kolkata")

    fin_inputs = {"income": income}
    profile = {
        "city": city,
        "housing": housing,
        "transport": vehicle,
        "food": food,
        "family_size": family_size,
    }
    res = calculate(fin_inputs, profile, cfg)
    # For compatibility with any callers still expecting old keys, include Breakdown-capitalized
    return {
        "City": city,
        "Total Expenses": res["total_expenses"],
        "Estimated Savings": res["savings"],
        "Suggested SIP Investment": max(0.0, res["savings"] * 0.30),
        "Breakdown": {
            "Rent": res["breakdown"]["rent"],
            "Transport": res["breakdown"]["transport"],
            "Food": res["breakdown"]["food"],
            "Family Misc": float(_FAMILY_MISC_PER_MEMBER * max(1, int(float(family_size)))),
            "Others": float(res["breakdown"]["misc"] - (_FAMILY_MISC_PER_MEMBER * max(1, int(float(family_size))))),
        },
    }
