# FinMate - Your Personal Finance & Investment Buddy

<img src="https://github.com/SouravUpadhyay7/FinMate/blob/main/assets/finmate%20webp.jpg?raw=true" width="600"/>

## Overview
FinMate is a Streamlit-based web application that helps you understand your monthly finances, get concise investment suggestions, and export a professional PDF report. It guides you through a simple multi-step wizard and stores your reports locally so you can revisit them later in the History section.

Key capabilities include:
- Analyze monthly expenses and estimated savings based on your city, lifestyle, and family size
- Get straightforward investment advice tailored to your income and goal
- Generate and download a polished PDF report
- Save runs to a local SQLite database and access them later from the History page

## Prerequisites
- Python 3.9 or newer is recommended
- A working internet connection to install Python dependencies
- No external API keys or cloud services are required

## Setup
Follow these steps to get the app running locally:

1) Clone the repository
- Using HTTPS:
  git clone https://github.com/kavia-common/finmate-18605-18612.git
  cd finmate-18605-18612

2) Create and activate a virtual environment
- macOS/Linux:
  python3 -m venv .venv
  source .venv/bin/activate
- Windows (PowerShell):
  py -3 -m venv .venv
  .\.venv\Scripts\Activate.ps1

3) Install dependencies
- From the project root where requirements.txt is located:
  pip install -r FinMate-18605/requirements.txt

## Run the app
From the repository root, start Streamlit and point it to the app entrypoint:
- macOS/Linux/Windows:
  streamlit run FinMate-18605/app.py

This launches the FinMate app in your browser (typically at http://localhost:8501).

## Local persistence and reports
FinMate uses local, file-based storage. All persistence is handled within the repository folder so everything stays on your machine.

- SQLite database
  - The app initializes a SQLite database file automatically on startup.
  - Location: FinMate-18605/finmate.db
  - Initialization and operations are implemented in utils/persistence.py (init_db, upsert_profile, save_run, save_pdf, list_profiles, list_reports).
  - The database contains tables for profiles, inputs, results, advice, and reports. No additional setup is required.

- Reports directory
  - Generated PDF reports and snapshots are saved under FinMate-18605/reports.
  - The app ensures this directory exists at runtime and will create it if missing.
  - When you save a run, the PDF is written with a timestamped filename such as report-p<profileId>-r<runId>-<timestamp>.pdf.
  - The History page reads from the database to list saved reports and allows you to download them.

- In-memory history snapshots
  - The app also writes a small JSON snapshot to FinMate-18605/reports for quick reference when pressing “Save to History” even if the database write fails.

## Using the app
The app opens with a left sidebar to navigate between the Wizard and History pages.

- Multi-step wizard
  1. Profile & Demographics
     - Enter your name, age, city (Kolkata or Jharkhand), family size, housing, transport, and food preference.
     - Inputs are validated for completeness and reasonable values.
  2. Income & Goals
     - Provide your monthly income, savings goal, goal purpose, and any additional note regarding extra expenses.
  3. Review & Calculate
     - Review your inputs and click “Calculate Report” to run the analysis.
     - The app computes total expenses, estimated savings, and a suggested SIP. It also builds an expense breakdown chart.
  4. Advice & Report
     - View the results, a pie chart of expenses, and tailored investment suggestions.
     - Download a PDF of your report.
     - Click “Save to History” to store the run in the local database and save the PDF into the reports directory.

- History page
  - Create or select a profile to filter saved runs.
  - View generated reports with timestamps, download PDFs, or open a preview if supported.
  - Reports are listed from newest to oldest.

## Configuration
- No API keys or external services are required.
- City-specific configuration files live under FinMate-18605/config (kolkata.json, jharkhand.json).
- The calculator loads and applies these settings automatically based on the city you select in the wizard.

## Troubleshooting
- Streamlit not found or other missing packages
  - Ensure your virtual environment is activated and run:
    pip install -r FinMate-18605/requirements.txt

- Permission errors creating FinMate-18605/reports or writing files
  - Make sure you have write permissions in the project directory.
  - You can manually create the directory if needed:
    mkdir -p FinMate-18605/reports

- Report generation issues (reportlab/matplotlib)
  - The app uses reportlab and matplotlib to generate PDFs and charts.
  - If you encounter platform-specific build issues, install system packages commonly required by reportlab (for example, on Debian/Ubuntu):
    sudo apt-get update && sudo apt-get install -y libfreetype6-dev libjpeg-dev zlib1g-dev
  - Then reinstall Python dependencies inside your virtual environment:
    pip install --no-cache-dir -r FinMate-18605/requirements.txt

- Database file locked
  - Close other running instances of the app that might be accessing finmate.db and try again.

## Project structure
The important files and folders are:

- FinMate-18605/app.py
  - Main Streamlit application with the multi-step wizard, History page, PDF export, and persistence hooks.
- FinMate-18605/utils/
  - calculator.py: Loads city config and calculates expenses/savings breakdown.
  - investment_advisor.py: Produces rule-based investment guidance.
  - report_generator.py: Builds the PDF report using reportlab and optional chart image.
  - persistence.py: Local SQLite database and filesystem helpers for profiles, runs, and PDFs.
  - validators.py: Input validation utilities used by the wizard.
- FinMate-18605/config/
  - kolkata.json, jharkhand.json: City-specific configuration values for calculator assumptions.
- FinMate-18605/assets/
  - Static images (e.g., logo, sample reports).
- FinMate-18605/reports/
  - Generated at runtime; holds timestamped PDF reports and JSON snapshots.

## Commands quick reference
- Create venv (macOS/Linux):
  python3 -m venv .venv && source .venv/bin/activate
- Create venv (Windows PowerShell):
  py -3 -m venv .venv; .\.venv\Scripts\Activate.ps1
- Install dependencies:
  pip install -r FinMate-18605/requirements.txt
- Run app:
  streamlit run FinMate-18605/app.py

## License
This project is provided as-is for demonstration and evaluation. If you plan to use this beyond evaluation, please add or update the LICENSE file accordingly.

## Contributing
Contributions are welcome. Please open issues or pull requests to improve FinMate.
