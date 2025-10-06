# app.py
# Multi-step Streamlit wizard with session state and placeholders for persistence and PDF hooks.

import os
from io import BytesIO
import datetime
import json
from pathlib import Path

import streamlit as st
import matplotlib.pyplot as plt

from utils.calculator import calculate_finance, load_city_config, calculate
from utils.report_generator import generate_pdf
from utils.persistence import init_db, upsert_profile, save_run, save_pdf, list_profiles, list_reports
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

# Initialize local SQLite DB (safe to call multiple times)
try:
    with st.spinner("Initializing local storage..."):
        init_db()
except Exception as _e:
    # Non-fatal for UI; saving may warn later
    st.warning("Local storage initialization failed; history may not be available.")

# -----------------------------------------------------------------------------
# Helpers and session state
# -----------------------------------------------------------------------------
def _currency_fmt(value: float, decimals: int = 0) -> str:
    """Format a number as a currency string for UI display only."""
    try:
        fmt = f"₹{float(value):,.{decimals}f}" if decimals > 0 else f"₹{float(value):,.0f}"
        return fmt
    except Exception:
        return str(value)

def _human_time(ts: str | None) -> str:
    """Return a human-readable local timestamp from ISO string."""
    if not ts:
        return "Unknown time"
    try:
        dt = datetime.datetime.fromisoformat(ts)
    except Exception:
        return str(ts)
    # display in local time if naive
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)

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
        "pie_chart_bytes": None,    # PNG bytes of the pie chart (legacy key)
        "chart_bytes": None,        # Standardized key for PNG chart bytes
        "history": [],              # simple in-memory history list
        "active_page": "Wizard",    # "Wizard" or "History"
        "active_profile_id": None,  # Selected profile id for History section
        "created_profile_flag": False,  # for gentle toast after create
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
    """Placeholder: Save a history entry. Currently appends to in-memory list and writes a JSON snapshot to reports dir."""
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
    try:
        plt.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        png_bytes = buf.read()
    except Exception:
        png_bytes = None
    finally:
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

        nav_buttons(prev_label="Back", next_label="Continue", show_prev=False, show_next=False)

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
                numeric_results = None
                with st.spinner("Running financial analysis..."):
                    try:
                        base_dir = os.path.dirname(__file__)
                        # Graceful handling of missing or malformed configs done inside load_city_config
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

                # If results exist, build pie and advice
                if st.session_state.results:
                    # Build pie chart from numeric breakdown if present
                    breakdown = None
                    if isinstance(numeric_results, dict):
                        br = numeric_results.get("breakdown", {})
                        if isinstance(br, dict):
                            breakdown = br
                    with st.spinner("Preparing charts..."):
                        png = make_pie_chart(breakdown if isinstance(breakdown, dict) else {})
                        st.session_state.pie_chart_bytes = png
                        st.session_state.chart_bytes = png

                    # Investment advice: use normalized signature (financial inputs + profile)
                    try:
                        fin_inputs_norm = {
                            "income": fin.get("income", 0),
                            "goal_amount": fin.get("savings_goal", 0),
                            "goal_purpose": fin.get("goal_purpose", "") or "",
                        }
                        profile_norm_for_advice = {
                            "city": prof.get("city", "Kolkata"),
                            "family_size": prof.get("family_size", 1),
                            "housing": prof.get("housing", "Own"),
                            "transport": prof.get("vehicle", prof.get("transport", "Public transport")),
                            "food": prof.get("food", "Cook at home"),
                        }
                        with st.spinner("Generating investment suggestions..."):
                            advice = suggest_investments(fin_inputs_norm, profile_norm_for_advice)
                    except Exception as e:
                        advice = [f"Advice generation error: {e}"]
                    st.session_state.advice = advice

                    # Handle zero/negative savings gracefully with friendly nudge
                    try:
                        sv = float(st.session_state.results.get("savings", 0.0) or 0.0)
                        if sv <= 0:
                            st.info("Your estimated savings are zero or negative. Consider reducing expenses or setting a smaller short-term goal.")
                    except Exception:
                        pass

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
            # Provide a compact user-friendly summary before raw JSON
            totals = st.session_state.results
            try:
                st.write(
                    f"Income: {_currency_fmt(totals.get('income', 0))} • "
                    f"Expenses: {_currency_fmt(totals.get('total_expenses', 0))} • "
                    f"Savings: {_currency_fmt(totals.get('savings', 0))} • "
                    f"Suggested SIP: {_currency_fmt(totals.get('suggested_sip', 0))}"
                )
            except Exception:
                pass
            st.json(st.session_state.results)

    # Step 4: Advice & Report
    elif step == "Advice & Report":
        st.header("Advice & Report")

        # Display analysis results
        if st.session_state.results:
            st.subheader("Financial Analysis")
            totals = st.session_state.results
            try:
                st.write(
                    f"Income: {_currency_fmt(totals.get('income', 0))} • "
                    f"Expenses: {_currency_fmt(totals.get('total_expenses', 0))} • "
                    f"Savings: {_currency_fmt(totals.get('savings', 0))} • "
                    f"Suggested SIP: {_currency_fmt(totals.get('suggested_sip', 0))}"
                )
            except Exception:
                pass
            st.json(st.session_state.results)

        # Show pie chart
        chart_bytes = st.session_state.chart_bytes or st.session_state.pie_chart_bytes
        if chart_bytes:
            st.subheader("Expense Breakdown")
            try:
                st.image(chart_bytes, caption="Expense Breakdown", use_column_width=True)
            except Exception:
                st.info("Chart is unavailable due to an internal error.")

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

            # Pass raw bytes if present; generator accepts bytes/BytesIO
            pie_buf = st.session_state.chart_bytes or st.session_state.pie_chart_bytes or None

            # Prepare optional metadata for header
            user_profile = (st.session_state.profile or {})
            user_name = user_profile.get("name") or None
            user_city = user_profile.get("city") or None
            # Prefer official logo if exists; fallback to bundled image
            logo_path = "assets/logo.png" if os.path.exists(os.path.join(os.path.dirname(__file__), "assets", "logo.png")) else "assets/finmate webp.jpg"

            # PDF generation
            try:
                with st.spinner("Generating PDF report..."):
                    pdf_buffer = generate_pdf(
                        results_for_pdf,
                        pie_chart_buffer=pie_buf,
                        user_name=user_name,
                        city=user_city,
                        logo_path=logo_path,
                    )
                st.download_button(
                    label="📥 Download PDF Report",
                    data=pdf_buffer,
                    file_name="FinMate_Report.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"PDF generation failed: {e}")
                pdf_buffer = None

        # Save to history and persist PDF/report if possible
        if st.button("Save to History"):
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "profile": st.session_state.profile,
                "financials": st.session_state.financials,
                "results": st.session_state.results,
                "advice": st.session_state.advice,
            }
            save_history_entry(entry)
            # Attempt DB-backed persistence
            try:
                with st.spinner("Saving run to history..."):
                    # Upsert minimal profile (no email flow in UI; will create by name only)
                    profile_payload = dict(st.session_state.profile or {})
                    # upsert_profile handles missing email
                    profile_id = upsert_profile(profile_payload)

                    # Save run snapshot
                    fin_inputs_norm = {
                        "income": st.session_state.financials.get("income"),
                        "goal_amount": st.session_state.financials.get("savings_goal"),
                        "goal_purpose": st.session_state.financials.get("goal_purpose", ""),
                        "misc_note": st.session_state.financials.get("other_expenses_note", ""),
                    }
                    results_numeric = dict(st.session_state.results or {})
                    advice_list = list(st.session_state.advice or [])
                    run_id = save_run(profile_id, fin_inputs_norm, results_numeric, advice_list)

                    # Save PDF if available
                    if pdf_buffer is not None:
                        try:
                            pdf_bytes = pdf_buffer.getvalue() if hasattr(pdf_buffer, "getvalue") else bytes(pdf_buffer or b"")
                        except Exception:
                            pdf_bytes = b""
                        try:
                            file_path = save_pdf(run_id, profile_id, pdf_bytes)
                            st.success(f"Saved to history and file: {os.path.basename(file_path)}")
                        except Exception as e:
                            st.warning(f"Run saved, but PDF file could not be saved: {e}")
                    else:
                        st.success("Saved to history.")
            except Exception as e:
                st.warning(f"Saved to in-memory history, but persistent save failed: {e}")
        moved = nav_buttons(prev_label="Back", next_label="Finish", show_prev=True, show_next=False)
        if moved == "prev":
            st.session_state.step = "Review & Calculate"
            st.experimental_rerun()

# -----------------------------------------------------------------------------
# History Page
# -----------------------------------------------------------------------------
if st.session_state.active_page == "History":
    st.header("History")

    # Profiles area: select or create a profile
    with st.container():
        st.subheader("Select Profile")
        profiles = []
        try:
            with st.spinner("Loading profiles..."):
                profiles = list_profiles()
        except Exception as e:
            st.warning(f"Could not load profiles: {e}")

        # Build display names
        display_items = []
        index_map = {}
        for idx, p in enumerate(profiles):
            nm = p.get("name") or "(Unnamed)"
            mail = p.get("email") or ""
            label = f"{nm} ({mail})" if mail else nm
            display_items.append(label)
            index_map[idx] = p.get("id")

        selected_index = None
        if display_items:
            # preselect previous active profile if present
            try:
                if st.session_state.active_profile_id is not None:
                    # find index for the current active id
                    for i, p in enumerate(profiles):
                        if p.get("id") == st.session_state.active_profile_id:
                            selected_index = i
                            break
            except Exception:
                selected_index = None

            choose_index = st.selectbox(
                "Profiles",
                options=list(range(len(display_items))),
                format_func=lambda i: display_items[i],
                index=selected_index if selected_index is not None else 0,
            )
            st.session_state.active_profile_id = index_map.get(choose_index)
        else:
            st.info("No profiles yet. Create one below to start saving and viewing report history.")
            st.session_state.active_profile_id = None

        with st.expander("➕ Create a new profile"):
            with st.form("create_profile_form"):
                new_name = st.text_input("Name", value="")
                new_email = st.text_input("Email (optional)", value="")
                new_city = st.selectbox("City", ["Kolkata", "Jharkhand"])
                new_family = st.number_input("Family size", min_value=1, step=1, value=1)
                new_housing = st.selectbox("Housing", ["Own", "Rent"])
                new_transport = st.selectbox("Transport", ["Own vehicle", "Public transport"])
                new_food = st.selectbox("Food", ["Cook at home", "Order food mostly"])
                create_clicked = st.form_submit_button("Create Profile")

            if create_clicked:
                payload = {
                    "name": new_name,
                    "email": new_email.strip() or None,
                    "city": new_city,
                    "family_size": int(new_family),
                    "housing": new_housing,
                    "transport": new_transport,
                    "food": new_food,
                }
                ok, errs = validate_user_profile({
                    "name": payload["name"],
                    "email": payload["email"],
                    "city": payload["city"],
                    "family_size": payload["family_size"],
                    "housing": payload["housing"],
                    "transport": payload["transport"],
                    "food": payload["food"],
                })
                if not ok:
                    for fld, msg in errs.items():
                        st.error(f"{fld}: {msg}")
                else:
                    try:
                        with st.spinner("Creating profile..."):
                            pid = upsert_profile(payload)
                        st.session_state.active_profile_id = pid
                        st.success("Profile created.")
                        st.session_state.created_profile_flag = True
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Failed to create profile: {e}")

    st.divider()

    # Reports list for selected profile
    st.subheader("Saved Reports")
    pid = st.session_state.active_profile_id
    if not pid:
        st.info("Select a profile to view its report history.")
    else:
        try:
            with st.spinner("Fetching reports..."):
                reports = list_reports(pid)
        except Exception as e:
            reports = []
            st.error(f"Failed to fetch reports: {e}")

        if not reports:
            st.info("No reports saved yet for this profile.")
        else:
            # Render each report with timestamp and actions
            for rep in reports:
                created = _human_time(rep.get("created_at"))
                file_path = rep.get("file_path") or ""
                file_name = os.path.basename(file_path) if file_path else "(missing)"
                run_id = rep.get("run_id")

                with st.container():
                    cols = st.columns([4, 3, 3, 3])
                    with cols[0]:
                        st.write(f"• {file_name}")
                        st.caption(f"Run #{run_id} • Created: {created}")
                    # Download button
                    btn_key = f"dl_{rep.get('id')}"
                    with cols[1]:
                        if file_path and os.path.exists(file_path):
                            try:
                                # Read bytes safely
                                with open(file_path, "rb") as f:
                                    data = f.read()
                                st.download_button(
                                    label="Download PDF",
                                    data=data,
                                    file_name=file_name,
                                    mime="application/pdf",
                                    key=btn_key,
                                )
                            except Exception as e:
                                st.warning(f"Unavailable for download: {e}")
                        else:
                            st.button("Download PDF", disabled=True, key=btn_key + "_disabled")
                    # Open button (show in-app)
                    with cols[2]:
                        open_key = f"open_{rep.get('id')}"
                        can_open = file_path and os.path.exists(file_path)
                        if st.button("Open", key=open_key, disabled=not bool(can_open)):
                            try:
                                with open(file_path, "rb") as f:
                                    pdf_bytes = f.read()
                                st.session_state[f"preview_{rep.get('id')}"] = pdf_bytes
                            except Exception as e:
                                st.warning(f"Could not open file: {e}")
                    # Path info
                    with cols[3]:
                        # show parent dir in muted text for clarity across OS
                        if file_path:
                            st.caption(f"Location: {Path(file_path).parent}")

                # Inline preview if opened
                preview_key = f"preview_{rep.get('id')}"
                if st.session_state.get(preview_key):
                    with st.expander(f"Preview: {file_name}", expanded=False):
                        st.download_button(
                            label="Download (from preview)",
                            data=st.session_state[preview_key],
                            file_name=file_name,
                            mime="application/pdf",
                            key=f"dl_prev_{rep.get('id')}",
                        )
                        st.write("Preview embedded below:")
                        try:
                            st.pdf(st.session_state[preview_key])  # Streamlit 1.39+ provides st.pdf; if not available, fallback below
                        except Exception:
                            st.info("Inline PDF preview not supported in this environment.")

st.caption("FinMate Beta v1.2")
