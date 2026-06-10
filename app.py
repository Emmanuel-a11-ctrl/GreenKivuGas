import streamlit as st
import pandas as pd
import datetime
import random
import os
import gspread
from google.oauth2.service_account import Credentials
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

st.set_page_config(page_title="GreenKivuGas | CNG Intelligence", layout="wide", page_icon="🌱")

# ------------------------------- General Configuration --------------------------------
# Simple Login Credentials (for demonstration purposes)
USERNAME = "greenkivugas"
PASSWORD = "Q12028"

# -------------------------------
# Google Sheets configuration (optional)
# -------------------------------
SPREADSHEET_ID = "1V_m6QaWXORyV65wssDkd8ITft9_Sd0UoqhYuB-r6lLE"   # your actual ID
SHEET_NAME = "Leads"
SERVICE_ACCOUNT_JSON = "greenkivu_sa.json"      # local file (upload to your repo)

# -------------------------------
# CSV fallback (local file – always works)
# -------------------------------
CSV_FALLBACK_PATH = "leads.csv"

# No os.makedirs needed – the file will be created in the current directory


# -------------------------------
# 4. LEAD CAPTURE (Google Sheets + CSV fallback)
# -------------------------------
# -------------------------------
# Configuration
# -------------------------------
# Google Sheets (optional – will be used if credentials exist)
SPREADSHEET_ID = "1V_m6QaWXORyV65wssDkd8ITft9_Sd0UoqhYuB-r6lLE"          # <--- CHANGE THIS
SHEET_NAME = "Leads"
SERVICE_ACCOUNT_JSON = "greenkivu_sa.json"      # local file (upload to your repo)

# CSV fallback – always works (local file, no permissions issues)
CSV_FALLBACK_PATH = "leads.csv"

# -------------------------------
# Helper: is this Google Colab?
# -------------------------------
def is_colab():
    try:
        import google.colab
        return True
    except ImportError:
        return False

# If running in Colab and Drive is mounted, we can optionally use Drive path for CSV
if is_colab():
    try:
        from google.colab import drive
        drive.mount('/content/drive', force_remount=False)
        # Optional: use Drive path as additional fallback
        DRIVE_CSV_PATH = "/content/drive/MyDrive/GASMETH_Chatbot/online_inquiry.csv"
        os.makedirs(os.path.dirname(DRIVE_CSV_PATH), exist_ok=True)
    except:
        pass
else:
    DRIVE_CSV_PATH = None

# -------------------------------
# 4. LEAD CAPTURE (Google Sheets + local CSV fallback)
# -------------------------------
def save_lead_to_gsheets(name, phone, email, industry, notes):
    """Attempt to write to Google Sheets using service account."""
    try:
        import json
        import gspread
        from google.oauth2.service_account import Credentials

        # Use Streamlit secrets if available, otherwise fallback to JSON file
        try:
            service_account_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        except Exception:
            # Fallback to file (for local testing)
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON, scopes=scopes)

        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        timestamp = datetime.datetime.now().isoformat()
        sheet.append_row([timestamp, name, phone, email, industry, notes])
        return True, "Saved to Google Sheets"
    except Exception as e:
        return False, str(e)

def save_lead_to_csv(name, phone, email, industry, notes, path=CSV_FALLBACK_PATH):
    """Save to a local CSV file (always works)."""
    try:
        data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "name": name, "phone": phone, "email": email,
            "industry": industry, "notes": notes
        }
        df_new = pd.DataFrame([data])
        if os.path.exists(path):
            df_existing = pd.read_csv(path)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_combined = df_new
        df_combined.to_csv(path, index=False)
        return True, f"Saved to {path}"
    except Exception as e:
        return False, str(e)

def save_lead(name, phone, email, industry, notes=""):
    # Try Google Sheets first (if credentials exist and file is present)
    if os.path.exists(SERVICE_ACCOUNT_JSON) and SPREADSHEET_ID != "1V_m6QaWXORyV65wssDkd8ITft9_Sd0UoqhYuB-r6lLE":
        success, msg = save_lead_to_gsheets(name, phone, email, industry, notes)
        if success:
            st.success("✅ Thank you! Your request has been saved to Google Sheets, GasMeth representative will contact you within 24 hours.")
            return
        else:
            st.warning(f"⚠️ Google Sheets failed: {msg}. Falling back to CSV.")

    # Fallback to local CSV
    success2, msg2 = save_lead_to_csv(name, phone, email, industry, notes)
    if success2:
        st.success(f"✅ Thank you! Your request has been saved locally ({msg2}), GasMeth representative will contact you within 24 hours.")
    else:
        st.error(f"❌ Could not save your request. Please try again later. Error: {msg2}")

    # If running in Colab and Drive is available, also save a copy there (optional)
    if is_colab() and DRIVE_CSV_PATH and os.path.exists("/content/drive"):
        save_lead_to_csv(name, phone, email, industry, notes, path=DRIVE_CSV_PATH)

# -------------------------------
# 5. CHATBOT (predefined answers) – unchanged
# -------------------------------
predefined_answers = {
    "Is CNG safe for cooking?": "Yes, CNG is safe for cooking. It is lighter than air, disperses quickly, and has a narrow flammability range.",
    "How much to convert my diesel truck?": "For a 340 HP truck, conversion kit costs USD$1,500-$2,000. Installation adds USD $500-$1,000.",
    "What financing options do you offer?": "We provide pay-from-savings financing: zero down payment, monthly repayment = 20% of your fuel savings.",
    "How much can I save switching from LPG?": "You save about 53% on fuel cost. For a restaurant using 50 MMBTU/month, that's ~$1,016 monthly savings.",
    "What is the CNG price per MMBTU?": "CNG price is fixed at USD15.00-USD27.00 per MMBTU.",
    "How do I schedule a site visit?": "Use the 'Book a Site Visit' tab above.",
    "Is CNG cleaner than wood?": "Yes, CNG produces no smoke, no particulate matter, and 30% less CO2 than wood.",
    "What is the conversion cost for a small car?": "Typically USD 800 - USD1,500.",
    "How long is the payback period?": "Usually 6-18 months depending on fuel usage."
}

def answer_question(question: str) -> str:
    return predefined_answers.get(question, "I'm not sure. Please ask another question or contact our team via the 'Book a Site Visit' tab.")

# -------------------------------
# 6. SAVINGS CALCULATOR (unchanged)
# -------------------------------
CONVERSION_FACTORS = {
    ("diesel", "litres"): 0.0358,
    ("petrol", "litres"): 0.0323,
    ("lpg", "kg"):       0.0472,
    ("hfo", "litres"):   0.0398,
    ("wood", "kg"):      0.0150,
    ("coal", "kg"):      0.0250,
}

FUEL_PRICE_PER_MMBTU = {
    "diesel": 40.73,
    "petrol": 60.14,
    "lpg":    38.32,
    "hfo":    26.42,
    "wood":    6.0,
    "coal":    5.5,
}

FUEL_TO_CNG_PRICE = {
    "diesel":  27,
    "petrol":  27,
    "lpg":     18,
    "hfo":     15,
    "wood":    15,
    "coal":    15,
}

def mmbtu_from_fuel(fuel_type: str, amount: float, unit: str) -> float:
    factor = CONVERSION_FACTORS.get((fuel_type, unit), 0.0)
    return amount * factor

def get_cng_price_for_fuel(fuel_type: str) -> float:
    return FUEL_TO_CNG_PRICE.get(fuel_type, 15.0)

def calculate_savings(current_fuel: str, monthly_amount: float, unit: str,
                      custom_cng_price: float = None) -> tuple:
    mmbtu = mmbtu_from_fuel(current_fuel, amount=monthly_amount, unit=unit)
    if mmbtu == 0:
        return None, None, None
    current_price = FUEL_PRICE_PER_MMBTU.get(current_fuel)
    if current_price is None:
        return None, None, None
    if custom_cng_price is not None:
        cng_price = custom_cng_price
    else:
        cng_price = get_cng_price_for_fuel(current_fuel)
    current_cost = mmbtu * current_price
    cng_cost = mmbtu * cng_price
    savings = current_cost - cng_cost
    return current_cost, cng_cost, savings

# -------------------------------
# 7. CARBON CREDITS CALCULATOR (unchanged)
# -------------------------------
EMISSION_FACTORS_KG_CO2_PER_MMBTU = {
    "diesel": 74.15,
    "petrol": 71.25,
    "lpg":    63.1,
    "hfo":    78.8,
    "wood":   112.0,
    "coal":   95.6,
}
CNG_EMISSION_FACTOR = 51.0
CARBON_CREDIT_PRICE_USD_PER_TON = 50.0

def calculate_carbon_credits(current_fuel: str, monthly_amount: float, unit: str) -> dict:
    mmbtu = mmbtu_from_fuel(current_fuel, amount=monthly_amount, unit=unit)
    if mmbtu == 0:
        return None
    current_emissions_kg = mmbtu * EMISSION_FACTORS_KG_CO2_PER_MMBTU.get(current_fuel, 0)
    cng_emissions_kg = mmbtu * CNG_EMISSION_FACTOR
    reduction_kg = current_emissions_kg - cng_emissions_kg
    if reduction_kg <= 0:
        return None
    reduction_tons = reduction_kg / 1000.0
    monthly_credit_value = reduction_tons * CARBON_CREDIT_PRICE_USD_PER_TON
    annual_credit_value = monthly_credit_value * 12
    return {
        "monthly_reduction_tons": reduction_tons,
        "annual_reduction_tons": reduction_tons * 12,
        "monthly_credit_usd": monthly_credit_value,
        "annual_credit_usd": annual_credit_value,
        "mmbtu": mmbtu,
    }

def carbon_credits_calculator_page():
    st.header("🌿 Carbon Credits Calculator")
    st.markdown("Estimate the CO₂ emissions reduction and carbon credit revenue when switching from a conventional fuel to CNG.")
    st.caption(f"Carbon credit price = **${CARBON_CREDIT_PRICE_USD_PER_TON} / ton CO₂eq**")

    col1, col2 = st.columns(2)
    with col1:
        fuel = st.selectbox("Current fuel", ["diesel", "petrol", "lpg", "hfo", "wood", "coal"], key="cc_fuel")
        amount = st.number_input("Monthly consumption", min_value=0.0, step=10.0, value=100.0, key="cc_amount")
        unit = st.selectbox("Unit", ["litres", "kg"], key="cc_unit")
    with col2:
        if st.button("Calculate carbon credits", key="cc_btn"):
            if amount <= 0:
                st.warning("Please enter a positive monthly consumption.")
                return
            result = calculate_carbon_credits(fuel, amount, unit)
            if result is None:
                st.error("Could not calculate. Check fuel/unit combination or emissions data.")
            else:
                st.success(f"Based on {amount} {unit} of {fuel} per month:")
                st.metric("Monthly CO₂ reduction", f"{result['monthly_reduction_tons']:.2f} tons")
                st.metric("Annual CO₂ reduction", f"{result['annual_reduction_tons']:.2f} tons")
                st.metric("Monthly carbon credit value", f"${result['monthly_credit_usd']:,.2f}")
                st.metric("Annual carbon credit value", f"${result['annual_credit_usd']:,.2f}")
                st.info("💡 These credits can be sold on voluntary carbon markets or used for internal sustainability reporting.")

# -------------------------------
# 8. DASHBOARD (changed: added leads display and download button)
# -------------------------------
def show_dashboard(df: pd.DataFrame, alerts):
    st.header("📊 Executive Dashboard")

    # --- Added Lead Download Functionality ---
    st.subheader("🔒 Lead Management (Admin Login Required)")

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        with st.form("login_form"):
            admin_username = st.text_input("Username")
            admin_password = st.text_input("Password", type="password")
            login_button = st.form_submit_button("Login")

            if login_button:
                if admin_username == USERNAME and admin_password == PASSWORD:
                    st.session_state['logged_in'] = True
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")

    if st.session_state['logged_in']:
        if os.path.exists(CSV_FALLBACK_PATH):
            st.write("Here are the leads submitted via the 'Book a Site Visit' form:")
            df_leads = pd.read_csv(CSV_FALLBACK_PATH)
            st.dataframe(df_leads)

            with open(CSV_FALLBACK_PATH, "rb") as file:
                st.download_button(
                    label="📥 Download Leads CSV",
                    data=file,
                    file_name="leads.csv",
                    mime="text/csv",
                    key="download_leads_csv"
                )
        else:
            st.info("No leads have been submitted yet.")
        if st.button("Logout"): # Added logout button
            st.session_state['logged_in'] = False
            st.rerun()

def cng_bot_page():
    st.header("💬 Ask the CNG Bot")
    st.markdown("Ask about conversion costs, savings, financing, etc.")
    common_questions = list(predefined_answers.keys())
    selected = st.selectbox("Choose a common question:", [""] + common_questions)
    custom = st.text_input("Or type your own question:")
    user_question = custom.strip() if custom else selected
    if st.button("Ask"):
        if not user_question:
            st.warning("Please select or type a question.")
        else:
            answer = answer_question(user_question)
            st.markdown(f"**🤖 Bot:** {answer}")

def savings_calculator_page():
    st.header("💰 Savings Calculator")
    col1, col2 = st.columns(2)
    with col1:
        fuel = st.selectbox("Current fuel", ["diesel", "petrol", "lpg", "hfo", "wood", "coal"])
        amount = st.number_input("Monthly consumption", min_value=0.0, step=10.0, value=100.0)
        unit = st.selectbox("Unit", ["litres", "kg"])
    with col2:
        if st.button("Calculate savings"):
            if amount > 0:
                current, cng, save = calculate_savings(fuel, amount, unit)
                if current is not None:
                    st.metric("Current monthly cost", f"${current:,.2f}")
                    st.metric("CNG monthly cost", f"${cng:,.2f}")
                    st.metric("Monthly savings", f"${save:,.2f}", delta=f"{(save/current)*100:.1f}% less")
                else:
                    st.error("Unit conversion not available.")
            else:
                st.warning("Enter a positive amount.")

def site_visit_page():
    st.header("📝 Book a Site Visit")
    with st.form("visit_form"):
        name = st.text_input("Full name*")
        phone = st.text_input("Phone number*")
        email = st.text_input("Email*")
        industry = st.selectbox("Industry", ["Industrial", "Autofuel (transport)", "Cooking (restaurant/school)", "Other"])
        notes = st.text_area("Any specific questions or preferred visit date?")
        submitted = st.form_submit_button("Request Visit")
        if submitted:
            if name and phone and email:
                save_lead(name, phone, email, industry, notes)
            else:
                st.error("Please fill in all required fields.")

# -------------------------------
# 10. MAIN APP
# -------------------------------
def main():
    st.title("🌱 GreenKivuGas")
    st.caption("CNG from Lake Kivu – Smart management, conversion insights, savings & site visits")

    if "service" not in st.session_state:
        # Original data models and service logic were removed, so these calls will fail.
        # This section will likely require re-integration or removal if not needed.
        # For now, commenting out to avoid further errors related to missing classes/functions.
        # svc = GreenKivuGasService()
        # generate_sample_data(svc)
        # st.session_state.service = svc
        # service = st.session_state.service # This line would also need to be re-evaluated

        # Placeholder for service if previous lines are commented out
        class MockService:
            def get_dataframe(self): return pd.DataFrame()
            def check_for_alerts(self): return []
        st.session_state.service = MockService()

    service = st.session_state.service

    menu = st.sidebar.selectbox("Menu", [
        "📊 Dashboard",
        "💬 CNG safety & FAQs Bot",
        "💰 Savings Calculator",
        "🌿 Carbon Credits Calculator",
        "📝 Book a Site Visit"
    ])

    if menu == "📊 Dashboard":
        df = service.get_dataframe()
        alerts = service.check_for_alerts()
        show_dashboard(df, alerts)
    elif menu == "💬 CNG safety & FAQs Bot":
        cng_bot_page()
    elif menu == "💰 Savings Calculator":
        savings_calculator_page()
    elif menu == "🌿 Carbon Credits Calculator":
        carbon_credits_calculator_page()
    elif menu == "📝 Book a Site Visit":
        site_visit_page()

if __name__ == "__main__":
    main()
