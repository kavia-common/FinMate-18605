"""
Validation helpers for FinMate.

This module provides small, UI-agnostic validation utilities and
model-level validators for UserProfile and FinancialInputs.

All functions return validation booleans and error messages rather than
raising exceptions, so callers can decide how to surface issues (e.g., in UI).

PUBLIC INTERFACES:
- is_required
- is_positive_number
- in_range
- is_valid_email
- validate_user_profile
- validate_financial_inputs
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

# Simple, permissive email regex for basic format validation (no external deps)
_EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


# PUBLIC_INTERFACE
def is_required(value: Any, field_name: str) -> Tuple[bool, Optional[str]]:
    """Check that a required value is present and not an empty string."""
    if value is None:
        return False, f"{field_name} is required."
    if isinstance(value, str) and value.strip() == "":
        return False, f"{field_name} is required."
    return True, None


# PUBLIC_INTERFACE
def is_positive_number(value: Any, field_name: str) -> Tuple[bool, Optional[str]]:
    """Check that the value is an int/float and strictly positive (> 0)."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return False, f"{field_name} must be a number."
    if num <= 0:
        return False, f"{field_name} must be greater than 0."
    return True, None


# PUBLIC_INTERFACE
def in_range(
    value: Any,
    field_name: str,
    min_value: float | None = None,
    max_value: float | None = None,
) -> Tuple[bool, Optional[str]]:
    """Check that the numeric value falls within optional [min, max] bounds (inclusive)."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return False, f"{field_name} must be a number."
    if min_value is not None and num < float(min_value):
        return False, f"{field_name} must be at least {min_value}."
    if max_value is not None and num > float(max_value):
        return False, f"{field_name} must be at most {max_value}."
    return True, None


# PUBLIC_INTERFACE
def is_valid_email(value: str | None) -> Tuple[bool, Optional[str]]:
    """Basic email format validator using a simple regex."""
    if value is None or str(value).strip() == "":
        # Email is optional in our models, treat empty as valid; presence should be checked via is_required if needed.
        return True, None
    val = str(value).strip()
    if _EMAIL_REGEX.match(val):
        return True, None
    return False, "Email format looks invalid."


# PUBLIC_INTERFACE
def validate_user_profile(profile: Any) -> Tuple[bool, Dict[str, str]]:
    """
    Validate a UserProfile-like object (dataclass or dict).
    Returns (is_valid, errors_dict).
    Expected fields:
    - name (required, non-empty)
    - email (optional, if present must be valid)
    - city (required, must be one of known cities if provided)
    - family_size (required, positive integer)
    - housing ("Own" | "Rent")
    - transport ("Own vehicle" | "Public transport")
    - food ("Cook at home" | "Order food mostly")
    - age (optional, if present must be within [18, 120])
    """
    errors: Dict[str, str] = {}

    # Helper to get attribute from dataclass or key from dict
    def get(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    name = get(profile, "name")
    ok, msg = is_required(name, "Name")
    if not ok and msg:
        errors["name"] = msg

    email = get(profile, "email")
    ok, msg = is_valid_email(email)
    if not ok and msg:
        errors["email"] = msg

    city = get(profile, "city", "")
    ok, msg = is_required(city, "City")
    if not ok and msg:
        errors["city"] = msg
    else:
        allowed_cities = {"Kolkata", "Jharkhand"}
        if str(city) not in allowed_cities:
            errors["city"] = f"City must be one of: {', '.join(sorted(allowed_cities))}."

    family_size = get(profile, "family_size")
    ok, msg = is_positive_number(family_size, "Family size")
    if not ok and msg:
        errors["family_size"] = msg
    else:
        # must be integer >= 1
        try:
            if int(float(family_size)) < 1:
                errors["family_size"] = "Family size must be at least 1."
        except Exception:
            errors["family_size"] = "Family size must be an integer."

    housing = get(profile, "housing", "")
    if housing:
        if str(housing) not in {"Own", "Rent"}:
            errors["housing"] = "Housing must be either 'Own' or 'Rent'."
    else:
        errors["housing"] = "Housing is required."

    transport = get(profile, "transport", get(profile, "vehicle", ""))  # app may store 'vehicle'
    if transport == "":
        errors["transport"] = "Transport is required."
    else:
        if str(transport) not in {"Own vehicle", "Public transport"}:
            errors["transport"] = "Transport must be 'Own vehicle' or 'Public transport'."

    food = get(profile, "food", "")
    if food == "":
        errors["food"] = "Food preference is required."
    else:
        if str(food) not in {"Cook at home", "Order food mostly"}:
            errors["food"] = "Food must be 'Cook at home' or 'Order food mostly'."

    age = get(profile, "age", None)
    if age is not None and str(age) != "":
        ok, msg = in_range(age, "Age", min_value=18, max_value=120)
        if not ok and msg:
            errors["age"] = msg

    return len(errors) == 0, errors


# PUBLIC_INTERFACE
def validate_financial_inputs(inputs: Any) -> Tuple[bool, Dict[str, str]]:
    """
    Validate a FinancialInputs-like object (dataclass or dict).
    Returns (is_valid, errors_dict).
    Expected fields:
    - income (required, positive number, reasonable upper bound check)
    - goal_amount (required, positive number)
    - goal_purpose (optional string)
    - misc_note (optional string)
    """
    errors: Dict[str, str] = {}

    def get(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    income = get(inputs, "income")
    ok, msg = is_positive_number(income, "Monthly income")
    if not ok and msg:
        errors["income"] = msg
    else:
        # Put a sanity upper bound (e.g., 1e8 per month) to avoid typos
        ok, msg = in_range(income, "Monthly income", min_value=1000, max_value=1e8)
        if not ok and msg:
            errors["income"] = msg

    goal_amount = get(inputs, "goal_amount", get(inputs, "savings_goal"))
    if goal_amount is None or str(goal_amount).strip() == "":
        errors["goal_amount"] = "Savings goal is required."
    else:
        ok, msg = is_positive_number(goal_amount, "Savings goal")
        if not ok and msg:
            errors["goal_amount"] = msg

    # goal_purpose and misc_note are optional; trim if present
    goal_purpose = get(inputs, "goal_purpose", "")
    if isinstance(goal_purpose, str) and len(goal_purpose.strip()) > 256:
        errors["goal_purpose"] = "Goal purpose is too long (max 256 characters)."

    misc_note = get(inputs, "misc_note", get(inputs, "other_expenses_note", ""))
    if isinstance(misc_note, str) and len(misc_note.strip()) > 500:
        errors["misc_note"] = "Additional note is too long (max 500 characters)."

    return len(errors) == 0, errors
