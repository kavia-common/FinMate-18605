# app.py
# Multi-step Streamlit wizard with session state and placeholders for persistence and PDF hooks.

import os
from io import BytesIO
import datetime
import json

import streamlit as st
import matplotlib.pyplot as plt

from utils.calculator import calculate_finance, load_city_config, calculate
from utils.report_generator import generate_pdf
from utils.investment_advisor import suggest_investments
from utils.validators import (
    validate_user_profile,
    validate_financial_inputs,
)

# Streamlit app configuration
st.set_page_config(page_title="FinMate", page_icon=":moneybag:", layout="centered")

# Ensure reports directory exists for saving reports/history artifacts
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Helpers and session state
# -----------------------------------------------------------------------------
def _currency_fmt(value: float) -> str:
    """Format a number as a currency string for UI display only."""
    try:
        return f"₹{float(value):,.0f}"
    except Exception:
        return str(value)

def init_state():
    """Initialize st.session_state defaults."""
    defaults = {
        "step": "Profile & Demographics",
        "profile": {
            "name": "",
            "age": 25,
            "city": "Kolkata",
            "family_size": 1,
            "housing": "Own",
            "vehicle": "Public transport",
            "food": "Cook at home",
        },
        "financials": {
            "income": 10000,
            "other_expenses_note": "",
            "savings_goal": 10000,
            "goal_purpose": "",
        },
        "results": None,            # calculator results
        "advice": None,             # investment advice list
        "pie_chart_bytes": None,    # PNG bytes of the pie chart
        "history": [],              # simple in-memory history list
        "active_page": "Wizard",    # "Wizard" or "History"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def nav_buttons(prev_label="Back", next_label="Next", show_prev=True, show_next=True):
    """Render navigation buttons for the wizard."""
    col1, col2, col3 = st.columns([1, 1, 1])
    moved = False
    with col1:
        if show_prev and st.button(f"← {prev_label}", use_container_width=True):
            moved = "prev"
    with col3:
        if show_next and st.button(f"{next_label} →", use_container_width=True):
            moved = "next"
    return moved

def save_history_entry(entry: dict):
    """Placeholder: Save a history entry. Currently appends to in-memory list and writes a JSON snapshot to reports dir.
    TODO: Replace with utils/persistence.py in step 1.7 for SQLite/file persistence.
    """
    st.session_state.history.append(entry)
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(REPORTS_DIR, f"history-{timestamp}.json")
        with open(path, "w") as f:
            json.dump(entry, f, indent=2, default=str)
    except Exception as e:
        st.warning(f"Could not write history snapshot: {e}")

def make_pie_chart(breakdown: dict) -> bytes | None:
    """Create a pie chart PNG bytes from a numeric breakdown dict."""
    if not breakdown or not isinstance(breakdown, dict):
        return None

    labels = []
    values = []
    for k, v in breakdown.items():
        if isinstance(v, (int, float)) and v > 0:
            labels.append(k)
            values.append(v)

    if not values:
        # Fallback to sample data
        labels = ["Sample Category 1", "Sample Category 2", "Sample Category 3"]
        values = [5000, 3000, 2000]

    fig, ax = plt.subplots(figsize=(10, 6))
    wedges, texts, autotexts = ax.pie(
        values,
        autopct="%1.1f%%",
        textprops={"color": "w", "fontweight": "bold"},
        shadow=True,
        startangle=90,
    )
    ax.axis("equal")
    ax.legend(wedges, [str(l) for l in labels], title="Expense Categories", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    png_bytes = buf.read()
    plt.close(fig)
    return png_bytes

# -----------------------------------------------------------------------------
# UI: Header and Navigation
# -----------------------------------------------------------------------------
init_state()

st.image("assets/finmate webp.jpg", width=150)
st.title("FinMate - Your Personal Finance & Investment Buddy")

# Top-level navigation: Wizard / History
nav = st.sidebar.radio("Navigate", ["Wizard", "History"], index=0 if st.session_state.active_page == "Wizard" else 1)
st.session_state.active_page = nav

# Wizard step order
steps = [
    "Profile & Demographics",
    "Income & Goals",
    "Review & Calculate",
    "Advice & Report",
]

# -----------------------------------------------------------------------------
# Wizard Pages
# -----------------------------------------------------------------------------
if st.session_state.active_page == "Wizard":
    step = st.session_state.step

    # Step 1: Profile & Demographics
    if step == "Profile & Demographics":
        st.header("Profile & Demographics")
        with st.form("profile_form"):
            name = st.text_input("Your name", value=st.session_state.profile.get("name", ""))
            age = st.number_input("Age", min_value=18, max_value=100, step=1, value=int(st.session_state.profile.get("age", 25)))
            city = st.selectbox("Select your city", ["Kolkata", "Jharkhand"], index=["Kolkata", "Jharkhand"].index(st.session_state.profile.get("city", "Kolkata")))
            family_size = st.number_input("Family members (including you)", min_value=1, step=1, value=int(st.session_state.profile.get("family_size", 1)))
            housing = st.selectbox("Housing", ["Own", "Rent"], index=["Own", "Rent"].index(st.session_state.profile.get("housing", "Own")))
            vehicle = st.selectbox("Transport", ["Own vehicle", "Public transport"], index=["Own vehicle", "Public transport"].index(st.session_state.profile.get("vehicle", "Public transport")))
            food = st.selectbox("Food preference", ["Cook at home", "Order food mostly"], index=["Cook at home", "Order food mostly"].index(st.session_state.profile.get("food", "Cook at home")))
            submitted = st.form_submit_button("Save & Continue")
        if submitted:
            # Update local state first
            st.session_state.profile.update({
                "name": name,
                "age": age,
                "city": city,
                "family_size": family_size,
                "housing": housing,
                "vehicle": vehicle,
                "food": food,
            })
            # Validate profile before moving forward
            is_ok, errs = validate_user_profile({
                "name": name,
                "age": age,
                "city": city,
                "family_size": family_size,
                "housing": housing,
                "transport": vehicle,  # validators accept 'transport' or 'vehicle'
                "food": food,
            })
            if not is_ok:
                for fld, msg in errs.items():
                    st.error(f"{fld}: {msg}")
            else:
                st.session_state.step = "Income & Goals"
                st.experimental_rerun()

        moved = nav_buttons(prev_label="Back", next_label="Continue", show_prev=False, show_next=False)

    # Step 2: Income & Goals
    elif step == "Income & Goals":
        st.header("Income & Goals")
        with st.form("income_form"):
            income = st.number_input("Monthly income (₹)", min_value=1000, step=500, value=int(st.session_state.financials.get("income", 10000)))
            savings_goal = st.number_input("Savings goal (₹)", min_value=1000, step=500, value=int(st.session_state.financials.get("savings_goal", 10000)))
            goal_purpose = st.text_input("Savings goal purpose", value=st.session_state.financials.get("goal_purpose", ""))
            other_expenses_note = st.text_input("Additional expenses note (e.g., EMI, healthcare)", value=st.session_state.financials.get("other_expenses_note", ""))
            submitted = st.form_submit_button("Save & Continue")
        if submitted:
            # Build payload and validate
            payload = {
                "income": int(income),
                "goal_amount": int(savings_goal),
                "goal_purpose": goal_purpose,
                "misc_note": other_expenses_note,
                "savings_goal": int(savings_goal),  # backward field for validator mapping
                "other_expenses_note": other_expenses_note,
            }
            is_ok, errs = validate_financial_inputs(payload)
            if not is_ok:
                for fld, msg in errs.items():
                    st.error(f"{fld}: {msg}")
            else:
                st.session_state.financials.update({
                    "income": int(income),
                    "savings_goal": int(savings_goal),
                    "goal_purpose": goal_purpose,
                    "other_expenses_note": other_expenses_note,
                })
                st.session_state.step = "Review & Calculate"
                st.experimental_rerun()

        moved = nav_buttons(prev_label="Back", next_label="Continue", show_prev=True, show_next=False)
        if moved == "prev":
            st.session_state.step = "Profile & Demographics"
            st.experimental_rerun()

    # Step 3: Review & Calculate
    elif step == "Review & Calculate":
        st.header("Review & Calculate")
        # Review summary
        st.subheader("Profile")
        prof = st.session_state.profile
        st.write(f"Name: {prof.get('name') or 'N/A'}")
        st.write(f"Age: {prof.get('age')} | City: {prof.get('city')} | Family size: {prof.get('family_size')}")
        st.write(f"Housing: {prof.get('housing')} | Transport: {prof.get('vehicle')} | Food: {prof.get('food')}")

        st.subheader("Financials")
        fin = st.session_state.financials
        st.write(f"Monthly income: {_currency_fmt(fin.get('income', 0))}")
        st.write(f"Savings goal: {_currency_fmt(fin.get('savings_goal', 0))}")
        st.write(f"Goal purpose: {fin.get('goal_purpose') or 'N/A'}")
        if fin.get("other_expenses_note"):
            st.write(f"Other notes: {fin.get('other_expenses_note')}")

        # Calculate button
        if st.button("Calculate Report"):
            # Validate before compute to ensure consistent state
            ok_prof, prof_errs = validate_user_profile({
                "name": prof.get("name"),
                "age": prof.get("age"),
                "city": prof.get("city"),
                "family_size": prof.get("family_size"),
                "housing": prof.get("housing"),
                "transport": prof.get("vehicle", prof.get("transport", "Public transport")),
                "food": prof.get("food"),
            })
            ok_fin, fin_errs = validate_financial_inputs({
                "income": fin.get("income"),
                "goal_amount": fin.get("savings_goal"),
                "goal_purpose": fin.get("goal_purpose", ""),
                "misc_note": fin.get("other_expenses_note", ""),
                "savings_goal": fin.get("savings_goal"),
                "other_expenses_note": fin.get("other_expenses_note", ""),
            })

            if not ok_prof or not ok_fin:
                for fld, msg in {**prof_errs, **fin_errs}.items():
                    st.error(f"{fld}: {msg}")
            else:
                # Run calculator with new API (numeric-only results)
                try:
                    base_dir = os.path.dirname(__file__)
                    city_cfg = load_city_config(base_dir, prof.get("city", "Kolkata"))
                    fin_inputs = {"income": fin.get("income", 0)}
                    profile_norm = {
                        "city": prof.get("city", "Kolkata"),
                        "housing": prof.get("housing", "Own"),
                        "transport": prof.get("vehicle", prof.get("transport", "Public transport")),
                        "food": prof.get("food", "Cook at home"),
                        "family_size": prof.get("family_size", 1),
                    }
                    numeric_results = calculate(fin_inputs, profile_norm, city_cfg)
                    # Also add a suggested SIP value here for convenience in UI and downstream usage
                    numeric_results["suggested_sip"] = max(0.0, float(numeric_results.get("savings", 0.0)) * 0.30)
                    st.session_state.results = numeric_results
                except Exception as e:
                    st.session_state.results = None
                    st.error(f"Calculation failed: {e}")
                    numeric_results = None

                # Build pie chart from numeric breakdown if present
                breakdown = None
                if isinstance(numeric_results, dict):
                    br = numeric_results.get("breakdown", {})
                    if isinstance(br, dict):
                        breakdown = br
                png = make_pie_chart(breakdown if isinstance(breakdown, dict) else {})
                st.session_state.pie_chart_bytes = png

                # Investment advice
                advice = suggest_investments(
                    fin.get("income", 0),
                    prof.get("family_size", 1),
                    prof.get("city", "Kolkata"),
                    fin.get("savings_goal", 0),
                    fin.get("goal_purpose", "") or "",
                )
                st.session_state.advice = advice

                st.success("Calculated. Proceed to Advice & Report.")
                st.session_state.step = "Advice & Report"
                st.experimental_rerun()

        moved = nav_buttons(prev_label="Back", next_label="Next", show_prev=True, show_next=False)
        if moved == "prev":
            st.session_state.step = "Income & Goals"
            st.experimental_rerun()

        # Show interim JSON if already computed
        if st.session_state.results:
            st.subheader("Current Results")
            st.json(st.session_state.results)

    # Step 4: Advice & Report
    elif step == "Advice & Report":
        st.header("Advice & Report")

        # Display analysis results
        if st.session_state.results:
            st.subheader("Financial Analysis")
            st.json(st.session_state.results)

        # Show pie chart
        if st.session_state.pie_chart_bytes:
            st.subheader("Expense Breakdown")
            st.image(st.session_state.pie_chart_bytes, caption="Expense Breakdown", use_column_width=True)

        # Show investment advice
        if st.session_state.advice:
            st.subheader("💡 Investment Advice")
            for tip in st.session_state.advice:
                st.write(f"- {tip}")

        # Generate PDF hook
        pdf_buffer = None
        if st.session_state.results:
            # Merge advice into results for PDF
            results_for_pdf = dict(st.session_state.results)
            if st.session_state.advice:
                results_for_pdf["investment_advice"] = st.session_state.advice

            pie_buf = BytesIO(st.session_state.pie_chart_bytes) if st.session_state.pie_chart_bytes else None
            # PDF generation
            pdf_buffer = generate_pdf(results_for_pdf, pie_buf)

            # Download button
            st.download_button(
                label="📥 Download PDF Report",
                data=pdf_buffer,
                file_name="FinMate_Report.pdf",
                mime="application/pdf"
            )

        # Save to history (placeholder persistence)
        if st.button("Save to History"):
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "profile": st.session_state.profile,
                "financials": st.session_state.financials,
                "results": st.session_state.results,
                "advice": st.session_state.advice,
            }
            save_history_entry(entry)
            st.success("Saved to history.")
        moved = nav_buttons(prev_label="Back", next_label="Finish", show_prev=True, show_next=False)
        if moved == "prev":
            st.session_state.step = "Review & Calculate"
            st.experimental_rerun()

# -----------------------------------------------------------------------------
# History Page
# -----------------------------------------------------------------------------
if st.session_state.active_page == "History":
    st.header("History")
    # Placeholder: In-memory entries and optional JSON files in reports directory
    # TODO: Replace with utils/persistence.py integration for SQLite/file persistence.
    if st.session_state.history:
        for i, item in enumerate(reversed(st.session_state.history), start=1):
            with st.expander(f"Entry {i} - {item.get('timestamp', '')}"):
                st.write("Profile:", item.get("profile"))
                st.write("Financials:", item.get("financials"))
                st.write("Results:")
                st.json(item.get("results"))
                st.write("Advice:")
                advice = item.get("advice") or []
                for tip in advice:
                    st.write(f"- {tip}")
    else:
        st.info("No history saved yet.")

st.caption("FinMate Beta v1.0")
