import streamlit as st
import pandas as pd
import datetime
import random
import plotly.express as px
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(page_title="GreenKivuGas | CNG Intelligence", layout="wide", page_icon="🌱")

# -------------------------------
# 1. DATA MODELS (same as before)
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
# 2. CORE SERVICE
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
# 3. SAMPLE DATA (10 each)
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
# 4. DASHBOARD (same as before)
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

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("Fill Level Distribution")
        fig = px.box(df, x="Type", y="Fill %", color="Type", title="Fill % per asset type")
        st.plotly_chart(fig, use_container_width=True)
    with col_chart2:
        st.subheader("Refill Urgency")
        urgency = df[df["Needs Refill"]].groupby("Type").size().reset_index(name="Count")
        if not urgency.empty:
            fig2 = px.bar(urgency, x="Type", y="Count", color="Type", title="Assets requiring refill")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.success("No immediate refill needs")
    
    st.subheader("🚨 Critical Alerts (15-30% or empty)")
    alert_df = df[df["Needs Refill"]].sort_values("Fill %")
    if not alert_df.empty:
        st.dataframe(alert_df[["ID", "Owner", "Type", "Fill %", "Current (kg)", "Capacity (kg)"]], use_container_width=True)
    else:
        st.info("No tanks currently need refill")
    
    st.subheader("📋 Complete Inventory")
    styled_df = df.style.background_gradient(subset=["Fill %"], cmap="YlOrRd", vmin=0, vmax=100)
    st.dataframe(styled_df, use_container_width=True)

# -------------------------------
# 5. NEW TABS
# -------------------------------
def cng_bot_tab():
    st.header("💬 Ask the CNG Bot")
    st.markdown("Ask me about **conversion costs**, **fuel savings**, **financing options**, or any GreenKivuGas topic.")
    
    # Predefined knowledge base
    knowledge = {
        "conversion cost": "Conversion to CNG typically costs between **1,500,000 - 3,500,000 RWF** for a small car, **4,000,000 - 8,000,000 RWF** for a bus, and **6,000,000 - 12,000,000 RWF** for a truck. Prices include cylinders, kit, and installation.",
        "savings": "CNG saves **40-60%** compared to petrol and **30-50%** compared to diesel. For a typical car driving 100 km/day, savings can reach **200,000 - 300,000 RWF per month**.",
        "financing": "We offer **lease-to-own** programs with 0% down payment, **bank loans** through partner banks (interest rates as low as 12% p.a.), and **government subsidies** for schools and public transporters.",
        "payback period": "The payback period for conversion is usually **6-18 months** depending on fuel usage.",
        "safety": "CNG cylinders are **extremely safe** – they undergo rigorous testing (fire, crash, puncture). They are 2-3x thicker than LPG cylinders.",
        "maintenance": "CNG engines run cleaner – oil changes are needed every 10,000 km instead of 5,000 km. Spark plugs last twice as long.",
    }
    
    user_question = st.text_input("Your question:")
    if user_question:
        q_lower = user_question.lower()
        response = "I'm not sure about that. Please ask about conversion costs, savings, financing, payback period, safety, or maintenance."
        for key, answer in knowledge.items():
            if key in q_lower:
                response = answer
                break
        st.info(f"🤖 **Bot:** {response}")
    
    st.markdown("---")
    st.markdown("📌 **Example questions:**")
    st.markdown("- How much does it cost to convert a bus?")
    st.markdown("- What are the monthly savings for a truck?")
    st.markdown("- Do you offer financing for schools?")

def savings_calculator_tab():
    st.header("💰 Savings Calculator")
    st.markdown("Compare your current fuel costs with CNG.")
    
    vehicle_type = st.selectbox("Vehicle type", ["Small Car", "Bus", "Truck", "School (cooking)"])
    
    if vehicle_type == "Small Car":
        daily_km = st.number_input("Average daily distance (km)", min_value=10, value=80)
        fuel_type = st.radio("Current fuel", ["Petrol", "Diesel"])
        if fuel_type == "Petrol":
            current_price_per_liter = 1350  # RWF
            avg_km_per_liter = 12
        else:
            current_price_per_liter = 1300  # RWF
            avg_km_per_liter = 15
        cng_km_per_kg = 16  # typical for small car
        cng_price_per_kg = 1500
        daily_kg_needed = daily_km / cng_km_per_kg
        daily_current_cost = (daily_km / avg_km_per_liter) * current_price_per_liter
        daily_cng_cost = daily_kg_needed * cng_price_per_kg
        monthly_saving = (daily_current_cost - daily_cng_cost) * 30
        st.metric("Monthly Saving (RWF)", f"{monthly_saving:,.0f}", delta=f"{(monthly_saving/(daily_current_cost*30))*100:.0f}% reduction")
        st.caption(f"Daily CNG consumption: {daily_kg_needed:.1f} kg | Daily current cost: {daily_current_cost:.0f} RWF → CNG cost: {daily_cng_cost:.0f} RWF")
    
    elif vehicle_type == "Bus":
        daily_km = st.number_input("Average daily distance (km)", min_value=50, value=200)
        current_diesel_price = 1300
        avg_bus_km_per_liter = 3.5
        cng_bus_km_per_kg = 4.5
        daily_liters = daily_km / avg_bus_km_per_liter
        daily_kg = daily_km / cng_bus_km_per_kg
        daily_diesel_cost = daily_liters * current_diesel_price
        daily_cng_cost = daily_kg * 1500
        monthly_saving = (daily_diesel_cost - daily_cng_cost) * 30
        st.metric("Monthly Saving (RWF)", f"{monthly_saving:,.0f}", delta="up to 40% savings")
    
    elif vehicle_type == "Truck":
        daily_km = st.number_input("Average daily distance (km)", min_value=100, value=300)
        current_diesel_price = 1300
        avg_truck_km_per_liter = 2.5
        cng_truck_km_per_kg = 3.2
        daily_liters = daily_km / avg_truck_km_per_liter
        daily_kg = daily_km / cng_truck_km_per_kg
        daily_diesel_cost = daily_liters * current_diesel_price
        daily_cng_cost = daily_kg * 1500
        monthly_saving = (daily_diesel_cost - daily_cng_cost) * 30
        st.metric("Monthly Saving (RWF)", f"{monthly_saving:,.0f}")
    
    else:  # School cooking
        st.write("For school kitchens, compare **LPG** vs **CNG**.")
        monthly_lpg_kg = st.number_input("Current monthly LPG consumption (kg)", min_value=100, value=500)
        lpg_price_per_kg = 1800
        cng_price_per_kg = 1500
        monthly_lpg_cost = monthly_lpg_kg * lpg_price_per_kg
        monthly_cng_cost = monthly_lpg_kg * cng_price_per_kg
        monthly_saving = monthly_lpg_cost - monthly_cng_cost
        st.metric("Monthly Saving (RWF)", f"{monthly_saving:,.0f}", delta=f"{ (monthly_saving/monthly_lpg_cost)*100:.0f}% reduction")
        st.caption(f"LPG cost: {monthly_lpg_cost:,.0f} RWF → CNG cost: {monthly_cng_cost:,.0f} RWF")

def site_visit_tab():
    st.header("📝 Book a Site Visit")
    st.markdown("Our engineers will assess your premises and provide a custom conversion quote.")
    with st.form("visit_form"):
        name = st.text_input("Full name")
        phone = st.text_input("Phone number")
        email = st.text_input("Email address")
        org_type = st.selectbox("Organization type", ["School", "Bus company", "Trucking company", "Private car owner", "Other"])
        preferred_date = st.date_input("Preferred date", min_value=datetime.date.today())
        message = st.text_area("Additional information (optional)")
        submitted = st.form_submit_button("Request Visit")
        if submitted:
            st.success(f"Thank you {name}! We will contact you within 24 hours to confirm a visit on {preferred_date}.")
            # In a real app, you would send this data to a database or email API.

# -------------------------------
# 6. MAIN APP WITH TABS
# -------------------------------
def main():
    st.title("🌱 GreenKivuGas")
    st.caption("CNG from Lake Kivu – Smart management, conversion insights, savings & site visits")
    
    if "service" not in st.session_state:
        svc = GreenKivuGasService()
        generate_sample_data(svc)
        st.session_state.service = svc
    service = st.session_state.service

    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "💬 CNG Bot", "💰 Savings Calculator", "📝 Book a Site Visit"])
    
    with tab1:
        df = service.get_dataframe()
        alerts = service.check_for_alerts()
        show_dashboard(df, alerts)
    
    with tab2:
        cng_bot_tab()
    
    with tab3:
        savings_calculator_tab()
    
    with tab4:
        site_visit_tab()
    
    # Sidebar for quick actions (still useful)
    st.sidebar.markdown("## Quick Management")
    with st.sidebar.expander("➕ Register New Tank"):
        with st.form("quick_register"):
            ttype = st.selectbox("Type", [t.value for t in UserType], key="qr_type")
            owner = st.text_input("Owner", key="qr_owner")
            cap = st.number_input("Capacity (kg)", min_value=1.0, key="qr_cap")
            curr = st.number_input("Current (kg)", min_value=0.0, max_value=cap, key="qr_curr")
            qrc = st.text_input("QR code", key="qr_code")
            if st.form_submit_button("Register"):
                try:
                    new_tank = Tank(
                        tank_id=f"{ttype.upper()}_{random.randint(100,999)}",
                        qr_code=qrc,
                        capacity_kg=cap,
                        current_fill_level_kg=curr,
                        user_type=UserType(ttype),
                        owner_name=owner
                    )
                    if service.register_tank(new_tank):
                        st.success(f"Registered {new_tank.tank_id}")
                        st.rerun()
                    else:
                        st.error("ID/QR exists")
                except Exception as e:
                    st.error(str(e))
    
    with st.sidebar.expander("🛒 Place Refill Order"):
        qr = st.text_input("Scan QR", key="order_qr")
        if qr:
            tank = service.get_tank_by_qr(qr)
            if tank:
                st.write(f"{tank.owner_name}: {tank.current_fill_level_kg:.1f}/{tank.capacity_kg} kg")
                if st.button("Place order (fill to full)"):
                    oid = service.place_refill_order(qr, None)
                    if oid:
                        st.success(f"Order {oid} placed. Complete in 'Complete Order' tab")
                    else:
                        st.error("Tank full or invalid")

if __name__ == "__main__":
    main()
