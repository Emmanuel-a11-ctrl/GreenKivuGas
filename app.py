import streamlit as st
import pandas as pd
import datetime
import random
import os
import gspread
from google.oauth2.service_account import Credentials
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, NamedTuple

st.set_page_config(page_title="GreenKivuCNG | CNG Intelligence", layout="wide", page_icon="🌱")

# --- Custom CSS for sidebar menu styling ---
st.markdown("""
<style>
    body {
        font-family: "Garamond", sans-serif;
        font-weight: bold;
    }
    .stRadio > label {
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 5px;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid transparent;
    }
    .stRadio > label:nth-of-type(1) { background-color: #e6f7ff; border-color: #91d5ff; }
    .stRadio > label:nth-of-type(2) { background-color: #f6ffed; border-color: #b7eb8f; }
    .stRadio > label:nth-of-type(3) { background-color: #fffbe6; border-color: #ffe58f; }
    .stRadio > label:nth-of-type(4) { background-color: #ffe6f7; border-color: #ffadd2; }
    .stRadio > label:nth-of-type(5) { background-color: #e8f9f8; border-color: #87e8de; }
    .stRadio > label:hover { opacity: 0.8; cursor: pointer; }
    .stRadio > label.st-dg.st-c7 { background-color: #bae7ff; border-color: #1890ff; }
</style>
""", unsafe_allow_html=True)

# ------------------------------- General Configuration --------------------------------
USERNAME = "greenkivugas"
PASSWORD = "Q12028"

# ------------------------------- Google Sheets configuration -------------------------------
SPREADSHEET_ID = "1V_m6QaWXORyV65wssDkd8ITft9_Sd0UoqhYuB-r6lLE"
SHEET_NAME = "Leads"
SERVICE_ACCOUNT_JSON = "greenkivu_sa.json"
CSV_FALLBACK_PATH = "leads.csv"

def is_colab():
    try:
        import google.colab
        return True
    except ImportError:
        return False

if is_colab():
    try:
        from google.colab import drive
        drive.mount('/content/drive', force_remount=False)
        DRIVE_CSV_PATH = "/content/drive/MyDrive/GASMETH_Chatbot/online_inquiry.csv"
        os.makedirs(os.path.dirname(DRIVE_CSV_PATH), exist_ok=True)
    except:
        pass
else:
    DRIVE_CSV_PATH = None

# ------------------------------- Lead Capture -------------------------------
def save_lead_to_gsheets(name, phone, email, industry, notes):
    try:
        import json
        import gspread
        from google.oauth2.service_account import Credentials
        try:
            service_account_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        except Exception:
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        timestamp = datetime.datetime.now().isoformat()
        sheet.append_row([timestamp, name, phone, email, industry, notes])
        return True, "Saved to Google Sheets"
    except Exception as e:
        return False, str(e)

def save_lead_to_csv(name, phone, email, industry, notes, path=CSV_FALLBACK_PATH):
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
    if os.path.exists(SERVICE_ACCOUNT_JSON) and SPREADSHEET_ID != "1V_m6QaWXORyV65wssDkd8ITft9_Sd0UoqhYuB-r6lLE":
        success, msg = save_lead_to_gsheets(name, phone, email, industry, notes)
        if success:
            st.success("✅ Thank you! Your request has been saved to Google Sheets, GasMeth representative will contact you within 24 hours.")
            return
        else:
            st.warning(f"⚠️ Google Sheets failed: {msg}. Falling back to CSV.")
    success2, msg2 = save_lead_to_csv(name, phone, email, industry, notes)
    if success2:
        st.success(f"✅ Thank you! Your request has been saved locally ({msg2}), GasMeth representative will contact you within 24 hours.")
    else:
        st.error(f"❌ Could not save your request. Please try again later. Error: {msg2}")
    if is_colab() and DRIVE_CSV_PATH and os.path.exists("/content/drive"):
        save_lead_to_csv(name, phone, email, industry, notes, path=DRIVE_CSV_PATH)

# ------------------------------- Chatbot -------------------------------
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

# ------------------------------- Shared Conversion & Emission Data -------------------------------
CONVERSION_FACTORS = {
    ("diesel", "litres"): 0.0358,
    ("petrol", "litres"): 0.0323,
    ("LPG", "kg"):       0.0472,
    ("HFO", "litres"):   0.0398,
    ("wood", "kg"):      0.0150,
    ("coal", "kg"):      0.0250,
}

FUEL_PRICE_PER_MMBTU = {
    "diesel": 54.06,
    "petrol": 60.14,
    "LPG":    38.32,
    "HFO":    26.42,
    "wood":    6.0,
    "coal":    5.5,
}

FUEL_TO_CNG_PRICE = {
    "diesel":  27,
    "petrol":  27,
    "LPG":     18,
    "HFO":     15,
    "wood":    15,
    "coal":    15,
}

EMISSION_FACTORS_KG_CO2_PER_MMBTU = {
    "diesel": 73.15,
    "petrol": 71.30,
    "LPG":    63.1,
    "HFO":    78.20,
    "wood":   93.60,
    "coal":   95.30,
}

# Default values (can be overridden in advanced settings)
DEFAULT_CNG_EMISSION_FACTOR = 12.0      # kg CO₂ / MMBtu
DEFAULT_CARBON_CREDIT_PRICE_USD = 50.0  # per ton

# Allowed units per fuel (for validation and dynamic UI)
ALLOWED_UNITS = {
    "diesel": ["litres"],
    "petrol": ["litres"],
    "LPG": ["kg"],
    "HFO": ["litres"],
    "wood": ["kg"],
    "coal": ["kg"],
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

# ------------------------------- IMPROVED CARBON CREDITS CALCULATOR -------------------------------
class CarbonCreditResult(NamedTuple):
    monthly_reduction_tons: float
    annual_reduction_tons: float
    monthly_credit_usd: float
    annual_credit_usd: float
    mmbtu: float

def calculate_carbon_credits_improved(
    current_fuel: str,
    monthly_amount: float,
    unit: str,
    cng_emission_factor: float = DEFAULT_CNG_EMISSION_FACTOR,
    credit_price_usd_per_ton: float = DEFAULT_CARBON_CREDIT_PRICE_USD,
) -> Optional[CarbonCreditResult]:
    mmbtu = mmbtu_from_fuel(current_fuel, monthly_amount, unit)
    if mmbtu == 0:
        return None
    current_emissions_kg = mmbtu * EMISSION_FACTORS_KG_CO2_PER_MMBTU.get(current_fuel, 0)
    cng_emissions_kg = mmbtu * cng_emission_factor
    reduction_kg = current_emissions_kg - cng_emissions_kg
    if reduction_kg <= 0:
        return None
    reduction_tons = reduction_kg / 1000.0
    monthly_credit = reduction_tons * credit_price_usd_per_ton
    return CarbonCreditResult(
        monthly_reduction_tons=reduction_tons,
        annual_reduction_tons=reduction_tons * 12,
        monthly_credit_usd=monthly_credit,
        annual_credit_usd=monthly_credit * 12,
        mmbtu=mmbtu,
    )

def carbon_credits_calculator_page():
    st.header("🌿 Carbon Credits Calculator")
    st.markdown("Estimate the CO₂ emissions reduction and carbon credit revenue when switching from a conventional fuel to CNG.")

    # Advanced settings expander
    with st.expander("⚙️ Advanced settings"):
        cng_ef = st.number_input(
            "CNG emission factor (kg CO₂ / MMBtu)",
            min_value=0.0,
            value=DEFAULT_CNG_EMISSION_FACTOR,
            step=0.5,
            help="Typical natural gas: 12.0 kg CO₂/MMBtu. Adjust if your CNG source is different (e.g., biogas)."
        )
        credit_price = st.number_input(
            "Carbon credit price (USD / ton CO₂)",
            min_value=0.0,
            value=DEFAULT_CARBON_CREDIT_PRICE_USD,
            step=5.0,
            help="Current voluntary market price. Update as needed."
        )

    col1, col2 = st.columns(2)
    with col1:
        fuel = st.selectbox("Current fuel", list(ALLOWED_UNITS.keys()), key="cc_fuel")
        # Dynamically show only allowed units for the selected fuel
        allowed_units = ALLOWED_UNITS[fuel]
        unit = st.selectbox("Unit", allowed_units, key="cc_unit")
        amount = st.number_input(
            "Monthly consumption",
            min_value=0.0,
            step=10.0,
            value=100.0,
            key="cc_amount",
        )
    with col2:
        if st.button("Calculate carbon credits", key="cc_btn"):
            if amount <= 0:
                st.warning("Please enter a positive monthly consumption.")
                return
            # Unit validation already handled by dynamic dropdown, but still safe
            if unit not in ALLOWED_UNITS.get(fuel, []):
                st.error(f"Unit '{unit}' is not allowed for {fuel}. Choose from {ALLOWED_UNITS[fuel]}.")
                return

            result = calculate_carbon_credits_improved(
                fuel, amount, unit,
                cng_emission_factor=cng_ef,
                credit_price_usd_per_ton=credit_price,
            )
            if result is None:
                st.info(
                    "No emission reduction calculated. "
                    "Possible reasons: unsupported fuel/unit, or CNG emissions are not lower than current fuel."
                )
            else:
                st.success(f"Based on {amount} {unit} of {fuel} per month:")
                st.metric("Monthly CO₂ reduction", f"{result.monthly_reduction_tons:.2f} tons")
                st.metric("Annual CO₂ reduction", f"{result.annual_reduction_tons:.2f} tons")
                st.metric("Monthly carbon credit value", f"${result.monthly_credit_usd:,.2f}")
                st.metric("Annual carbon credit value", f"${result.annual_credit_usd:,.2f}")
                st.info("💡 These credits can be sold on voluntary carbon markets or used for internal sustainability reporting.")

# ------------------------------- Dashboard, Bot, Savings, Site Visit -------------------------------
def show_dashboard(df: pd.DataFrame, alerts):
    st.header("📊 Compressed Natural Gas (CNG) Commercial Dashboard")
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
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

def cng_bot_page():
    st.header("💬 Ask about Compressed Natural Gas (CNG)")
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
            st.markdown(f"**🤖:** {answer}")

def savings_calculator_page():
    st.header("💰 Savings Calculator")
    col1, col2 = st.columns(2)
    with col1:
        fuel = st.selectbox("Current fuel", ["diesel", "petrol", "LPG", "HFO", "wood", "coal"])
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
    st.header("📝 Book a Site Visit/Online Enquiry Form")
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

# ------------------------------- Main App -------------------------------
def main():
    st.title("🍃GreenKivuCNG")
    st.caption("CNG from Lake Kivu – Smart management, conversion insights, Emission reductions, Carbon credits,savings & site visits")

    # Mock service (since original data models were removed)
    class MockService:
        def get_dataframe(self): return pd.DataFrame()
        def check_for_alerts(self): return []
    if "service" not in st.session_state:
        st.session_state.service = MockService()
    service = st.session_state.service

    menu = st.sidebar.radio("Menu", [
        "📊 Dashboard",
        "💬 Compressed Natural Gas (CNG) safety & FAQs",
        "💰 Savings Calculator",
        "🌿 Carbon Credits Calculator",
        "📝 Book a Site Visit"
    ])

    if menu == "📊 Dashboard":
        df = service.get_dataframe()
        alerts = service.check_for_alerts()
        show_dashboard(df, alerts)
    elif menu == "💬 Compressed Natural Gas (CNG) safety & FAQs": # Fixed: Removed extra space
        cng_bot_page()
    elif menu == "💰 Savings Calculator":
        savings_calculator_page()
    elif menu == "🌿 Carbon Credits Calculator":
        carbon_credits_calculator_page()
    elif menu == "📝 Book a Site Visit":
        site_visit_page()

if __name__ == "__main__":
    main()
