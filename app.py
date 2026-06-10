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
# 1. DATA MODELS (unchanged)
# -------------------------------
class UserType(Enum):
    SCHOOL = "school"
    BUS = "bus"
    TRUCK = "truck"
    SMALL_CAR = "small_car"

@dataclass
class Tank:
    tank_id: str
    qr_code: str
    capacity_kg: float
    current_fill_level_kg: float
    user_type: UserType
    owner_name: str
    last_refill_date: Optional[datetime.date] = None
    refill_threshold_low: float = 15.0
    refill_threshold_high: float = 30.0

    @property
    def fill_percent(self) -> float:
        return (self.current_fill_level_kg / self.capacity_kg) * 100 if self.capacity_kg else 0

    def needs_refill(self) -> bool:
        p = self.fill_percent
        return self.current_fill_level_kg <= 0 or (self.refill_threshold_low <= p <= self.refill_threshold_high)

@dataclass
class RefillOrder:
    order_id: str
    tank_id: str
    qr_code: str
    amount_kg: float
    order_date: datetime.datetime
    status: str
    total_price_rwf: float

# -------------------------------
# 2. CORE SERVICE (unchanged)
# -------------------------------
class GreenKivuGasService:
    PRICE_RWF_PER_KG = 1500.0

    def __init__(self):
        self.tanks: Dict[str, Tank] = {}
        self.orders: Dict[str, RefillOrder] = {}
        self.order_counter = 0

    def register_tank(self, tank: Tank) -> bool:
        if tank.tank_id in self.tanks:
            return False
        self.tanks[tank.tank_id] = tank
        return True

    def get_tank_by_qr(self, qr: str) -> Optional[Tank]:
        for t in self.tanks.values():
            if t.qr_code == qr:
                return t
        return None

    def update_consumption(self, tank_id: str, consumed_kg: float) -> bool:
        t = self.tanks.get(tank_id)
        if not t or consumed_kg > t.current_fill_level_kg:
            return False
        t.current_fill_level_kg -= consumed_kg
        return True

    def check_for_alerts(self) -> List[Tank]:
        return [t for t in self.tanks.values() if t.needs_refill()]

    def place_refill_order(self, qr_code: str, amount_kg: Optional[float] = None) -> Optional[str]:
        tank = self.get_tank_by_qr(qr_code)
        if not tank:
            return None
        if amount_kg is None:
            amount_kg = tank.capacity_kg - tank.current_fill_level_kg
            if amount_kg <= 0:
                return None
        self.order_counter += 1
        oid = f"ORD-{self.order_counter:05d}"
        self.orders[oid] = RefillOrder(
            order_id=oid,
            tank_id=tank.tank_id,
            qr_code=qr_code,
            amount_kg=amount_kg,
            order_date=datetime.datetime.now(),
            status="pending",
            total_price_rwf=amount_kg * self.PRICE_RWF_PER_KG
        )
        return oid

    def complete_refill(self, order_id: str) -> bool:
        order = self.orders.get(order_id)
        if not order or order.status != "pending":
            return False
        tank = self.tanks.get(order.tank_id)
        if not tank:
            return False
        tank.current_fill_level_kg = min(tank.capacity_kg, tank.current_fill_level_kg + order.amount_kg)
        tank.last_refill_date = datetime.date.today()
        order.status = "completed"
        return True

    def get_dataframe(self) -> pd.DataFrame:
        rows = []
        for t in self.tanks.values():
            rows.append({
                "ID": t.tank_id,
                "QR": t.qr_code,
                "Type": t.user_type.value,
                "Owner": t.owner_name,
                "Capacity (kg)": t.capacity_kg,
                "Current (kg)": round(t.current_fill_level_kg, 1),
                "Fill %": round(t.fill_percent, 1),
                "Needs Refill": t.needs_refill(),
                "Last Refill": t.last_refill_date
            })
        return pd.DataFrame(rows)

# -------------------------------
# 3. SAMPLE DATA (unchanged)
# -------------------------------
def generate_sample_data(service: GreenKivuGasService):
    def random_fill(cap):
        r = random.random()
        if r < 0.2:
            return cap * random.uniform(0, 0.05)
        elif r < 0.5:
            return cap * random.uniform(0.15, 0.30)
        else:
            return cap * random.uniform(0.31, 0.95)

    for i in range(1, 11):
        cap = random.choice([1000, 1200, 1500, 1800, 2000])
        service.register_tank(Tank(
            tank_id=f"SCH_{i:03d}",
            qr_code=f"QR_SCH_{i}",
            capacity_kg=cap,
            current_fill_level_kg=random_fill(cap),
            user_type=UserType.SCHOOL,
            owner_name=f"School {i} (Kigali)"
        ))
    for i in range(1, 11):
        cap = random.choice([80, 100, 120])
        service.register_tank(Tank(
            tank_id=f"BUS_{i:03d}",
            qr_code=f"QR_BUS_{i}",
            capacity_kg=cap,
            current_fill_level_kg=random_fill(cap),
            user_type=UserType.BUS,
            owner_name=f"Bus {i}"
        ))
    for i in range(1, 11):
        cap = random.choice([150, 200, 250, 300])
        service.register_tank(Tank(
            tank_id=f"TRK_{i:03d}",
            qr_code=f"QR_TRK_{i}",
            capacity_kg=cap,
            current_fill_level_kg=random_fill(cap),
            user_type=UserType.TRUCK,
            owner_name=f"Truck {i}"
        ))
    for i in range(1, 11):
        cap = random.choice([15, 20, 30, 40, 50])
        service.register_tank(Tank(
            tank_id=f"CAR_{i:03d}",
            qr_code=f"QR_CAR_{i}",
            capacity_kg=cap,
            current_fill_level_kg=random_fill(cap),
            user_type=UserType.SMALL_CAR,
            owner_name=f"Car {i}"
        ))

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
            st.success("✅ Thank you! Your request has been saved to Google Sheets.")
            return
        else:
            st.warning(f"⚠️ Google Sheets failed: {msg}. Falling back to CSV.")

    # Fallback to local CSV
    success2, msg2 = save_lead_to_csv(name, phone, email, industry, notes)
    if success2:
        st.success(f"✅ Thank you! Your request has been saved locally ({msg2}).")
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
# 8. DASHBOARD (unchanged)
# -------------------------------
def show_dashboard(df: pd.DataFrame, alerts: List[Tank]):
    st.header("📊 Executive Dashboard")
    total_tanks = len(df)
    total_capacity_kg = df["Capacity (kg)"].sum()
    total_current_kg = df["Current (kg)"].sum()
    avg_fill = (total_current_kg / total_capacity_kg) * 100 if total_capacity_kg else 0
    refill_needed = len(alerts)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total CNG Assets", total_tanks)
    with col2:
        st.metric("Total Capacity", f"{total_capacity_kg:,.0f} kg")
    with col3:
        st.metric("Current Inventory", f"{total_current_kg:,.0f} kg", delta=f"{avg_fill:.1f}% full")
    with col4:
        st.metric("🚨 Tanks Needing Refill", refill_needed, delta="15-30% rule" if refill_needed else "All good")

    st.subheader("Average Fill % by Asset Type")
    avg_fill_by_type = df.groupby("Type")["Fill %"].mean().reset_index()
    st.bar_chart(avg_fill_by_type.set_index("Type"))

    st.subheader("Refill Urgency (Assets needing refill)")
    urgency = df[df["Needs Refill"]].groupby("Type").size().reset_index(name="Count")
    if not urgency.empty:
        st.bar_chart(urgency.set_index("Type"))
    else:
        st.success("No immediate refill needs")

    st.subheader("🚨 Critical Alerts (15-30% or empty)")
    alert_df = df[df["Needs Refill"]].sort_values("Fill %")
    if not alert_df.empty:
        st.dataframe(alert_df[["ID", "Owner", "Type", "Fill %", "Current (kg)", "Capacity (kg)"]])
    else:
        st.info("No tanks currently need refill")

    st.subheader("📋 Complete Inventory")
    st.dataframe(df)

# -------------------------------
# 9. UI PAGES (all unchanged except site_visit_page uses new save_lead)
# -------------------------------
def register_tank_page(service):
    st.header("➕ Register New CNG Asset")
    with st.form("register_form"):
        ttype = st.selectbox("Type", [t.value for t in UserType])
        owner = st.text_input("Owner Name")
        capacity = st.number_input("Capacity (kg)", min_value=1.0, step=10.0)
        current = st.number_input("Current fill (kg)", min_value=0.0, max_value=capacity, step=1.0)
        qr = st.text_input("QR Code (unique)")
        submitted = st.form_submit_button("Register")
        if submitted:
            try:
                new_tank = Tank(
                    tank_id=f"{ttype.upper()}_{random.randint(100,999)}",
                    qr_code=qr,
                    capacity_kg=capacity,
                    current_fill_level_kg=current,
                    user_type=UserType(ttype),
                    owner_name=owner
                )
                if service.register_tank(new_tank):
                    st.success(f"✅ Registered {new_tank.tank_id}")
                    st.rerun()
                else:
                    st.error("ID or QR code already exists")
            except Exception as e:
                st.error(str(e))

def place_refill_page(service):
    st.header("🛒 Place Refill Order")
    qr = st.text_input("Scan QR Code")
    if qr:
        tank = service.get_tank_by_qr(qr)
        if tank:
            st.write(f"**{tank.owner_name}** ({tank.user_type.value}) – {tank.current_fill_level_kg:.1f} / {tank.capacity_kg} kg")
            method = st.radio("Amount", ["Fill to full", "Specify kg"])
            if method == "Fill to full":
                amount = None
            else:
                amount = st.number_input("kg", min_value=1.0, max_value=tank.capacity_kg - tank.current_fill_level_kg, step=1.0)
            if st.button("Place Order"):
                oid = service.place_refill_order(qr, amount)
                if oid:
                    st.success(f"📦 Order {oid} placed. Complete it in 'Complete Order' section.")
                else:
                    st.error("Order failed (tank full or invalid QR)")
        else:
            st.error("No tank found for that QR code")

def complete_order_page(service):
    st.header("✅ Complete a Refill Order")
    pending = [o for o in service.orders.values() if o.status == "pending"]
    if not pending:
        st.info("No pending orders")
    else:
        choice = st.selectbox("Select order", [f"{o.order_id} - {o.amount_kg} kg" for o in pending])
        order_id = choice.split()[0]
        if st.button("Complete Refill"):
            if service.complete_refill(order_id):
                st.success("Refill completed – inventory updated")
                st.rerun()
            else:
                st.error("Completion failed")

def simulate_consumption_page(service):
    st.header("⛽ Simulate Fuel Consumption")
    df = service.get_dataframe()
    options = {f"{row['ID']} – {row['Owner']}": row['ID'] for _, row in df.iterrows()}
    sel = st.selectbox("Select tank", list(options.keys()))
    kg = st.number_input("Consumed (kg)", min_value=0.0, step=1.0)
    if st.button("Record"):
        if service.update_consumption(options[sel], kg):
            st.success("Consumption recorded")
            tank = service.tanks[options[sel]]
            if tank.needs_refill():
                st.warning(f"⚠️ Now at {tank.fill_percent:.1f}% – needs refill")
        else:
            st.error("Not enough fuel")

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
        svc = GreenKivuGasService()
        generate_sample_data(svc)
        st.session_state.service = svc
    service = st.session_state.service

    menu = st.sidebar.selectbox("Menu", [
        "📊 Dashboard",
        "➕ Register Asset",
        "🛒 Place Refill Order",
        "✅ Complete Order",
        "⛽ Simulate Consumption",
        "💬 CNG safety & FAQs Bot",
        "💰 Savings Calculator",
        "🌿 Carbon Credits Calculator",
        "📝 Book a Site Visit"
    ])

    if menu == "📊 Dashboard":
        df = service.get_dataframe()
        alerts = service.check_for_alerts()
        show_dashboard(df, alerts)
    elif menu == "➕ Register Asset":
        register_tank_page(service)
    elif menu == "🛒 Place Refill Order":
        place_refill_page(service)
    elif menu == "✅ Complete Order":
        complete_order_page(service)
    elif menu == "⛽ Simulate Consumption":
        simulate_consumption_page(service)
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
