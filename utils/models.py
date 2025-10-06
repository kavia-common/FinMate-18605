"""
Data models for FinMate application.

This module defines lightweight dataclasses used to normalize data across
the calculator, advisor, and reporting utilities. These models intentionally
use only primitive types and basic dicts/lists for easy storage (e.g., JSON/SQLite).

PUBLIC INTERFACES:
- UserProfile
- FinancialInputs
- FinancialResults
- ReportMetadata
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime


# PUBLIC_INTERFACE
@dataclass
class UserProfile:
    """User profile and demographics used across the app."""
    name: str
    email: Optional[str] = None
    city: str = "Kolkata"
    family_size: int = 1
    # Normalized lifestyle/housing fields used by calculator and UI
    housing: str = "Own"  # "Own" | "Rent"
    transport: str = "Public transport"  # "Own vehicle" | "Public transport"
    food: str = "Cook at home"  # "Cook at home" | "Order food mostly"
    # Optional age or other metadata
    age: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation suitable for JSON/SQLite storage."""
        return asdict(self)


# PUBLIC_INTERFACE
@dataclass
class FinancialInputs:
    """Financial input parameters provided by the user for analysis and goals."""
    income: int  # Monthly income in INR (₹)
    goal_amount: int  # Savings goal amount (₹)
    goal_purpose: str = ""  # e.g., "Vacation", "Retirement"
    # Optional free-form note for additional expenses context
    misc_note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation suitable for JSON/SQLite storage."""
        # Keep primitives for storage; strings/ints only
        return asdict(self)


# PUBLIC_INTERFACE
@dataclass
class FinancialResults:
    """
    Results from the financial calculator and advisor.

    Fields:
    - totals: numeric summary values (e.g., income, total_expenses, estimated_savings, suggested_sip)
    - breakdown: category->amount dict for charting and PDF table
    - advice: list of investment tips/strings
    - extras: optional container for any additional result fields
    """
    totals: Dict[str, float] = field(default_factory=dict)
    breakdown: Dict[str, float] = field(default_factory=dict)
    advice: List[str] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a serializable dict, friendly to charts and PDF generation."""
        return {
            "totals": dict(self.totals),
            "breakdown": dict(self.breakdown),
            "advice": list(self.advice),
            "extras": dict(self.extras),
        }

    @staticmethod
    def from_legacy_calculator(payload: Dict[str, Any]) -> "FinancialResults":
        """
        Build FinancialResults from the current calculator output structure.

        Expected legacy keys in payload:
        - "Total Expenses": "₹<num>" or num
        - "Estimated Savings": "₹<num>" or num
        - "Suggested SIP Investment": "₹<num>" or num
        - "Breakdown": { category: amount, ... }
        Other keys are pushed into extras.
        """
        def _parse_currency(v: Any) -> float:
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                cleaned = v.replace("₹", "").replace(",", "").strip()
                try:
                    return float(cleaned)
                except ValueError:
                    return 0.0
            return 0.0

        totals: Dict[str, float] = {}
        totals["total_expenses"] = _parse_currency(payload.get("Total Expenses", 0))
        totals["estimated_savings"] = _parse_currency(payload.get("Estimated Savings", 0))
        totals["suggested_sip"] = _parse_currency(payload.get("Suggested SIP Investment", 0))

        breakdown = {}
        bd = payload.get("Breakdown") or {}
        if isinstance(bd, dict):
            for k, v in bd.items():
                breakdown[str(k)] = float(v) if isinstance(v, (int, float)) else _parse_currency(v)

        # Collect unknowns into extras but keep them JSON-friendly
        extras: Dict[str, Any] = {}
        for k, v in payload.items():
            if k in {"Total Expenses", "Estimated Savings", "Suggested SIP Investment", "Breakdown"}:
                continue
            extras[k] = v

        return FinancialResults(totals=totals, breakdown=breakdown, extras=extras)


# PUBLIC_INTERFACE
@dataclass
class ReportMetadata:
    """
    Metadata for generated reports, suitable for indexing and retrieval.

    Fields:
    - user_name: reference to user; we keep a denormalized string for simple storage
    - user_email: optional reference to user email
    - created_at: ISO 8601 timestamp string
    - pdf_path: optional filesystem path to generated PDF
    - tags: optional labels for quick filtering
    - notes: optional notes
    """
    user_name: str
    user_email: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    pdf_path: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation suitable for JSON/SQLite storage."""
        return asdict(self)
