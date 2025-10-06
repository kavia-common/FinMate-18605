"""
Local persistence utilities for FinMate.

Implements:
- SQLite database with tables: profiles, financial_inputs, results_summary, advice, reports
- Filesystem storage for generated PDF reports under <base_dir>/reports
- Helper functions for app integration:
    - init_db()
    - upsert_profile(profile)
    - get_or_create_profile_by_email(name, email)
    - get_profile(profile_id)
    - list_profiles()
    - save_run(profile_id, inputs, results, advice_list) -> run_id
    - save_pdf(run_id, profile_id, pdf_bytes) -> file_path
    - list_reports(profile_id)

Storage notes:
- DB file is stored at <base_dir>/finmate.db
- Report PDFs are saved in <base_dir>/reports with timestamped filenames.
- All DB interactions use sqlite3 from stdlib, one statement at a time, with simple error handling.
- JSON fields are stored as TEXT.

This module avoids any external services and keeps everything local to disk.
"""

from __future__ import annotations

import os
import sqlite3
import json
import datetime
from typing import Any, Dict, List, Optional, Tuple

# Resolve base directory as the FinMate-18605 root (parent of this file's directory)
_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DB_PATH = os.path.join(_BASE_DIR, "finmate.db")
_REPORTS_DIR = os.path.join(_BASE_DIR, "reports")


def _ensure_reports_dir() -> None:
    """Ensure the reports/ directory exists."""
    os.makedirs(_REPORTS_DIR, exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    """
    Get a sqlite3 connection with row factory for dict-like access.

    Connection is opened with default isolation level; callers should commit changes
    as operations are performed.
    """
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.datetime.utcnow().isoformat()


# PUBLIC_INTERFACE
def init_db() -> None:
    """
    Initialize the SQLite database and ensure all required tables exist.

    Tables:
    - profiles(id, name, email, age, city, family_size, housing, transport, food, created_at, updated_at)
    - financial_inputs(id, profile_id, run_id, income, goal_amount, goal_purpose, misc_note, raw_json, created_at)
    - results_summary(id, run_id, profile_id, income, total_expenses, savings, suggested_sip, breakdown_json, created_at)
    - advice(id, run_id, profile_id, advice_json, created_at)
    - reports(id, run_id, profile_id, file_path, created_at)

    Indices are added for common lookups.
    """
    _ensure_reports_dir()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        # profiles
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                age INTEGER,
                city TEXT,
                family_size INTEGER,
                housing TEXT,
                transport TEXT,
                food TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_profiles_name ON profiles(name)")

        # financial_inputs
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS financial_inputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                run_id INTEGER NOT NULL,
                income REAL,
                goal_amount REAL,
                goal_purpose TEXT,
                misc_note TEXT,
                raw_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_fin_inputs_profile ON financial_inputs(profile_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_fin_inputs_run ON financial_inputs(run_id)")

        # results_summary
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS results_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                income REAL,
                total_expenses REAL,
                savings REAL,
                suggested_sip REAL,
                breakdown_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_profile ON results_summary(profile_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_run ON results_summary(run_id)")

        # advice
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS advice (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                advice_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_advice_profile ON advice(profile_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_advice_run ON advice(run_id)")

        # reports
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                profile_id INTEGER,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_profile ON reports(profile_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_run ON reports(run_id)")

        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict."""
    return {k: row[k] for k in row.keys()}


# PUBLIC_INTERFACE
def upsert_profile(profile: Dict[str, Any]) -> int:
    """
    Insert or update a profile. If 'email' is provided and exists, update by email; otherwise insert new.

    Parameters:
    - profile: dict with keys such as name, email, age, city, family_size, housing, transport/vehicle, food

    Returns:
    - profile_id (int)
    """
    if not isinstance(profile, dict):
        raise ValueError("profile must be a dict")

    name = (profile.get("name") or "").strip()
    email = (profile.get("email") or None)
    age = profile.get("age")
    city = profile.get("city")
    family_size = profile.get("family_size")
    housing = profile.get("housing")
    transport = profile.get("transport", profile.get("vehicle"))
    food = profile.get("food")
    now = _now_iso()

    conn = _get_conn()
    try:
        cur = conn.cursor()
        profile_id: Optional[int] = None

        if email:
            cur.execute("SELECT id FROM profiles WHERE email = ?", (email,))
            row = cur.fetchone()
            if row:
                profile_id = int(row["id"])
                # update
                cur.execute(
                    """
                    UPDATE profiles
                    SET name = ?, age = ?, city = ?, family_size = ?, housing = ?, transport = ?, food = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (name, age, city, family_size, housing, transport, food, now, profile_id),
                )
                conn.commit()
                return profile_id

        # insert new
        cur.execute(
            """
            INSERT INTO profiles (name, email, age, city, family_size, housing, transport, food, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, email, age, city, family_size, housing, transport, food, now, now),
        )
        conn.commit()
        profile_id = int(cur.lastrowid)
        return profile_id
    finally:
        conn.close()


# PUBLIC_INTERFACE
def get_or_create_profile_by_email(name: str, email: str) -> int:
    """
    Get an existing profile id by email, or create a minimal one with provided name/email.

    Parameters:
    - name: user display name
    - email: unique email

    Returns:
    - profile_id (int)
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM profiles WHERE email = ?", (email,))
        row = cur.fetchone()
        if row:
            return int(row["id"])
    finally:
        conn.close()

    # Create minimal default profile
    payload = {
        "name": name,
        "email": email,
        "city": "Kolkata",
        "family_size": 1,
        "housing": "Own",
        "transport": "Public transport",
        "food": "Cook at home",
    }
    return upsert_profile(payload)


# PUBLIC_INTERFACE
def get_profile(profile_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a profile by id.

    Returns:
    - dict with profile fields or None if not found
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,))
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_dict(row)
    finally:
        conn.close()


# PUBLIC_INTERFACE
def list_profiles() -> List[Dict[str, Any]]:
    """
    List all profiles ordered by updated_at DESC.

    Returns:
    - List of dicts
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM profiles ORDER BY updated_at DESC")
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


# PUBLIC_INTERFACE
def save_run(
    profile_id: int,
    inputs: Dict[str, Any],
    results: Dict[str, Any],
    advice_list: List[str],
) -> int:
    """
    Persist a calculation run with its inputs snapshot, numeric results summary, and advice.

    Parameters:
    - profile_id: profile reference
    - inputs: dict with keys like income, goal_amount/ savings_goal, goal_purpose, misc_note
    - results: dict produced by calculator with keys income, total_expenses, savings, breakdown, suggested_sip (optional)
    - advice_list: list of strings with investment advice

    Returns:
    - run_id (int) used to relate inputs/results/advice and reports
    """
    # Create a new run id by inserting into results_summary first (or use a runs table; we derive run_id from that insert)
    # We'll follow a controlled sequence:
    now = _now_iso()

    # Extract normalized figures safely
    def _num(x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    income = _num(results.get("income", inputs.get("income")))
    total_expenses = _num(results.get("total_expenses", 0))
    savings = _num(results.get("savings", 0))
    suggested_sip = _num(results.get("suggested_sip", 0))
    breakdown = results.get("breakdown", {}) or {}

    # Insert a placeholder result row to obtain run_id
    conn = _get_conn()
    try:
        cur = conn.cursor()

        # Create a synthetic run_id by using results_summary rowid; we insert minimal then update with full data
        cur.execute(
            """
            INSERT INTO results_summary (run_id, profile_id, income, total_expenses, savings, suggested_sip, breakdown_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (0, profile_id, income, total_expenses, savings, suggested_sip, json.dumps(breakdown), now),
        )
        run_row_id = int(cur.lastrowid)

        # Update the row to set run_id = its own id (self-referential run id)
        cur.execute("UPDATE results_summary SET run_id = ? WHERE id = ?", (run_row_id, run_row_id))

        # Insert financial inputs snapshot
        fin_inputs = {
            "income": inputs.get("income"),
            "goal_amount": inputs.get("goal_amount", inputs.get("savings_goal")),
            "goal_purpose": inputs.get("goal_purpose", ""),
            "misc_note": inputs.get("misc_note", inputs.get("other_expenses_note", "")),
        }
        cur.execute(
            """
            INSERT INTO financial_inputs (profile_id, run_id, income, goal_amount, goal_purpose, misc_note, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                run_row_id,
                fin_inputs["income"],
                fin_inputs["goal_amount"],
                fin_inputs["goal_purpose"],
                fin_inputs["misc_note"],
                json.dumps(inputs),
                now,
            ),
        )

        # Insert advice row
        cur.execute(
            """
            INSERT INTO advice (run_id, profile_id, advice_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (run_row_id, profile_id, json.dumps(list(advice_list or [])), now),
        )

        conn.commit()
        return run_row_id
    finally:
        conn.close()


# PUBLIC_INTERFACE
def save_pdf(run_id: int, profile_id: int, pdf_bytes: bytes) -> str:
    """
    Save PDF bytes to the reports directory with a timestamped filename and record metadata.

    Parameters:
    - run_id: calculation run id to associate the report with
    - profile_id: user profile id
    - pdf_bytes: PDF file contents

    Returns:
    - file_path (absolute path) to the saved PDF on disk
    """
    _ensure_reports_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    # Safe filename: report-<profile>-<run>-<ts>.pdf
    filename = f"report-p{profile_id}-r{run_id}-{timestamp}.pdf"
    file_path = os.path.join(_REPORTS_DIR, filename)

    # Write file
    with open(file_path, "wb") as f:
        f.write(pdf_bytes or b"")

    # Record in DB
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO reports (run_id, profile_id, file_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (run_id, profile_id, file_path, _now_iso()),
        )
        conn.commit()
    finally:
        conn.close()

    return file_path


# PUBLIC_INTERFACE
def list_reports(profile_id: int) -> List[Dict[str, Any]]:
    """
    List report metadata for a profile, most recent first.

    Returns:
    - List of dicts with id, run_id, profile_id, file_path, created_at
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, run_id, profile_id, file_path, created_at
            FROM reports
            WHERE profile_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (profile_id,),
        )
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()
