
import streamlit as st
import pandas as pd
import datetime
import random
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

# -------------------------------
# 1. Enums & Data Models
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
    refill_threshold_low_percent: float = 15.0
    refill_threshold_high_percent: float = 30.0

    def get_usage_percentage(self) -> float:
        if self.capacity_kg == 0:
            return 0.0
        return (self.current_fill_level_kg / self.capacity_kg) * 100

    def needs_refill(self) -> bool:
        percent = self.get_usage_percentage()
        if self.current_fill_level_kg <= 0:
            return True
        if self.refill_threshold_low_percent <= percent <= self.refill_threshold_high_percent:
            return True
        return False

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
# 2. GreenKivuGas Management Service
# -------------------------------

class GreenKivuGasService:
    CNG_PRICE_PER_KG_RWF = 1500.0

    def __init__(self):
        self.tanks: Dict[str, Tank] = {}
        self.orders: Dict[str, RefillOrder] = {}
        self.order_counter = 0

    def register_tank(self, tank: Tank) -> bool:
        if tank.tank_id in self.tanks:
            return False
        self.tanks[tank.tank_id] = tank
        return True

    def get_tank_by_qr(self, qr_code: str) -> Optional[Tank]:
        for tank in self.tanks.values():
            if tank.qr_code == qr_code:
                return tank
        return None

    def update_consumption(self, tank_id: str, consumed_kg: float) -> bool:
        tank = self.tanks.get(tank_id)
        if not tank:
            return False
        new_level = tank.current_fill_level_kg - consumed_kg
        if new_level < 0:
            return False
        tank.current_fill_level_kg = new_level
        return True

    def check_for_alerts(self) -> List[Tank]:
        return [tank for tank in self.tanks.values() if tank.needs_refill()]

    def place_refill_order(self, qr_code: str, amount_kg: Optional[float] = None) -> Optional[str]:
        tank = self.get_tank_by_qr(qr_code)
        if not tank:
            return None
        if amount_kg is None:
            amount_kg = tank.capacity_kg - tank.current_fill_level_kg
            if amount_kg <= 0:
                return None
        self.order_counter += 1
        order_id = f"ORD-{self.order_counter:05d}"
        total_price = amount_kg * self.CNG_PRICE_PER_KG_RWF
        order = RefillOrder(
            order_id=order_id,
            tank_id=tank.tank_id,
            qr_code=qr_code,
            amount_kg=amount_kg,
            order_date=datetime.datetime.now(),
            status="pending",
            total_price_rwf=total_price
        )
        self.orders[order_id] = order
        return order_id

    def complete_refill(self, order_id: str) -> bool:
        order = self.orders.get(order_id)
        if not order or order.status != "pending":
            return False
        tank = self.tanks.get(order.tank_id)
        if not tank:
            return False
        tank.current_fill_level_kg += order.amount_kg
        if tank.current_fill_level_kg > tank.capacity_kg:
            tank.current_fill_level_kg = tank.capacity_kg
        tank.last_refill_date = datetime.date.today()
        order.status = "completed"
        return True

    def get_all_tanks_dataframe(self) -> pd.DataFrame:
        data = []
        for tank in self.tanks.values():
            data.append({
                "ID": tank.tank_id,
                "QR Code": tank.qr_code,
                "Type": tank.user_type.value,
                "Owner": tank.owner_name,
                "Capacity (kg)": tank.capacity_kg,
                "Current (kg)": round(tank.current_fill_level_kg, 1),
                "Fill %": round(tank.get_usage_percentage(), 1),
                "Needs Refill": tank.needs_refill(),
                "Last Refill": tank.last_refill_date
            })
        return pd.DataFrame(data)

# -------------------------------
# 3. Generate Sample Data
# -------------------------------

def generate_sample_data(service: GreenKivuGasService):
    def random_fill(capacity):
        r = random.random()
        if r < 0.2:
            return capacity * random.uniform(0, 0.05)
        elif r < 0.5:
            return capacity * random.uniform(0.15, 0.30)
        else:
            return capacity * random.uniform(0.31, 0.95)
    
    # 10 Schools
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
    # 10 Buses
    for i in range(1, 11):
        cap = random.choice([80, 100, 120])
        service.register_tank(Tank(
            tank_id=f"BUS_{i:03d}",
            qr_code=f"QR_BUS_{i}",
            capacity_kg=cap,
            current_fill_level_kg=random_fill(cap),
            user_type=UserType.BUS,
            owner_name=f"Bus {i} (Kigali City)"
        ))
    # 10 Trucks
    for i in range(1, 11):
        cap = random.choice([150, 200, 250, 300])
        service.register_tank(Tank(
            tank_id=f"TRK_{i:03d}",
            qr_code=f"QR_TRK_{i}",
            capacity_kg=cap,
            current_fill_level_kg=random_fill(cap),
            user_type=UserType.TRUCK,
            owner_name=f"Truck {i} (Logistics Co.)"
        ))
    # 10 Small Cars
    for i in range(1, 11):
        cap = random.choice([15, 20, 30, 40, 50])
        service.register_tank(Tank(
            tank_id=f"CAR_{i:03d}",
            qr_code=f"QR_CAR_{i}",
            capacity_kg=cap,
            current_fill_level_kg=random_fill(cap),
            user_type=UserType.SMALL_CAR,
            owner_name=f"Car {i} (Private Owner)"
        ))

# -------------------------------
# 4. Streamlit UI
# -------------------------------

st.set_page_config(page_title="GreenKivuGas", layout="wide")
st.title("🌱 GreenKivuGas")
st.subheader("CNG Management for Schools, Buses, Trucks & Small Cars")
st.markdown("**Powered by Lake Kivu – Clean Energy for Rwanda**")

if "service" not in st.session_state:
    service = GreenKivuGasService()
    generate_sample_data(service)
    st.session_state.service = service

service = st.session_state.service

action = st.sidebar.selectbox("Choose action", ["Dashboard", "Register New Tank", "Place Refill Order", "Complete Order", "Simulate Consumption"])

if action == "Dashboard":
    st.header("📊 Current Inventory")
    df = service.get_all_tanks_dataframe()
    type_filter = st.multiselect("Filter by type", options=df["Type"].unique(), default=df["Type"].unique())
    show_only_refill = st.checkbox("Show only tanks needing refill")
    filtered_df = df[df["Type"].isin(type_filter)]
    if show_only_refill:
        filtered_df = filtered_df[filtered_df["Needs Refill"] == True]
    st.dataframe(filtered_df, use_container_width=True)
    alerts = service.check_for_alerts()
    if alerts:
        st.warning(f"⚠️ {len(alerts)} tank(s) need refill (15-30% rule)!")
    else:
        st.success("All tanks are above the refill threshold ✅")

elif action == "Register New Tank":
    st.header("➕ Register a New CNG Tank")
    with st.form("register_form"):
        tank_type = st.selectbox("Type", [t.value for t in UserType])
        owner = st.text_input("Owner Name")
        capacity = st.number_input("Capacity (kg)", min_value=1.0, step=10.0)
        current_level = st.number_input("Current Fill Level (kg)", min_value=0.0, max_value=capacity, step=1.0)
        qr = st.text_input("QR Code (unique)")
        submitted = st.form_submit_button("Register")
        if submitted:
            try:
                new_tank = Tank(
                    tank_id=f"{tank_type.upper()}_{random.randint(100,999)}",
                    qr_code=qr,
                    capacity_kg=capacity,
                    current_fill_level_kg=current_level,
                    user_type=UserType(tank_type),
                    owner_name=owner
                )
                if service.register_tank(new_tank):
                    st.success(f"Tank {new_tank.tank_id} registered!")
                else:
                    st.error("Tank ID or QR already exists.")
            except Exception as e:
                st.error(f"Error: {e}")

elif action == "Place Refill Order":
    st.header("🛒 Place Refill Order")
    qr_input = st.text_input("Scan QR Code")
    if qr_input:
        tank = service.get_tank_by_qr(qr_input)
        if tank:
            st.write(f"**Tank:** {tank.owner_name} ({tank.user_type.value})")
            st.write(f"**Current:** {tank.current_fill_level_kg:.1f} / {tank.capacity_kg} kg")
            amount_method = st.radio("Refill amount", ["Fill to full capacity", "Specify amount (kg)"])
            if amount_method == "Fill to full capacity":
                amount = None
            else:
                amount = st.number_input("Amount (kg)", min_value=1.0, max_value=tank.capacity_kg - tank.current_fill_level_kg, step=1.0)
            if st.button("Place Order"):
                order_id = service.place_refill_order(qr_input, amount)
                if order_id:
                    st.success(f"Order {order_id} placed! Go to 'Complete Order' to finalize.")
                else:
                    st.error("Order failed (tank full or invalid).")
        else:
            st.error("No tank found for that QR code.")

elif action == "Complete Order":
    st.header("✅ Complete a Refill Order")
    pending = [o for o in service.orders.values() if o.status == "pending"]
    if not pending:
        st.info("No pending orders.")
    else:
        order_options = {f"{o.order_id} - {o.amount_kg} kg": o.order_id for o in pending}
        selected = st.selectbox("Select order to complete", list(order_options.keys()))
        if st.button("Complete Refill"):
            if service.complete_refill(order_options[selected]):
                st.success("Refill completed!")
            else:
                st.error("Failed to complete refill.")

elif action == "Simulate Consumption":
    st.header("⛽ Simulate Fuel Consumption")
    df = service.get_all_tanks_dataframe()
    tank_options = {f"{row['ID']} - {row['Owner']}": row['ID'] for _, row in df.iterrows()}
    selected_tank = st.selectbox("Select tank", list(tank_options.keys()))
    consumed = st.number_input("Consumed amount (kg)", min_value=0.0, step=1.0)
    if st.button("Record Consumption"):
        tank_id = tank_options[selected_tank]
        if service.update_consumption(tank_id, consumed):
            st.success("Consumption recorded.")
            tank = service.tanks[tank_id]
            if tank.needs_refill():
                st.warning(f"⚠️ {tank.owner_name} now needs refill ({tank.get_usage_percentage():.1f}%)")
        else:
            st.error("Consumption exceeds current fill level.")
