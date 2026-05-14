import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import math

# Professional wide layout configuration
st.set_page_config(layout="wide", page_title="AI Inventory Auditor Pro")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("Simulation Control")
    if st.button("🔄 Run New Simulation"):
        st.rerun()
    
    st.subheader("Inventory Policy")
    rop = st.number_input("Reorder Point (Units)", value=150)
    manual_order_qty = st.number_input("Selected Order Quantity", value=300)
    
    st.subheader("Cost & Demand Inputs")
    avg_demand = st.number_input("Avg. Daily Demand", value=20)
    std_demand = st.number_input("Demand Variability", value=5)
    lead_time = st.number_input("Lead Time (Days)", value=7)
    unit_cost = st.number_input("Unit Cost ($)", value=50)
    selling_price = st.number_input("Selling Price ($)", value=90)
    order_cost_fixed = st.number_input("Ordering Cost ($)", value=150)
    holding_cost_pct = st.number_input("Annual Holding Cost (%)", value=20.0) / 100
    opp_cost_pct = st.number_input("Cost of Capital (%)", value=12.0) / 100
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)
    duration = st.number_input("Simulation Duration (Days)", value=180)

# --- Financial & EOQ Math ---
annual_demand = avg_demand * 365
h_cost_per_unit = unit_cost * holding_cost_pct
calculated_eoq = math.sqrt((2 * annual_demand * order_cost_fixed) / h_cost_per_unit)

# Financial EOQ Calculation
daily_interest_rate = opp_cost_pct / 365
credit_gap_days = customer_credit - supplier_credit
credit_impact = unit_cost * (daily_interest_rate * credit_gap_days * 365)
h_financial = max(0.01, h_cost_per_unit + (unit_cost * opp_cost_pct) + credit_impact)
eoq_financial = math.sqrt((2 * annual_demand * order_cost_fixed) / h_financial)

# --- Simulation Engine ---
def run_simulation():
    inventory = int(1.25 * rop)
    cash_balance, ar_balance, ap_balance = 0, 0, 0
    pipeline_orders, pending_receivables, history = [], [], []
    daily_holding_rate = h_cost_per_unit / 365
    
    for day in range(duration):
        for o in list(pipeline_orders):
            if o['delivery_day'] == day:
                inventory += o['qty']
                ap_balance += o['payable_amount']
        
        daily_demand = max(0, int(np.random.normal(avg_demand, std_demand)))
        sales_units = min(inventory, daily_demand)
        stock_out_flag = 1 if daily_demand > (inventory + sales_units) else 0
        inventory -= sales_units
        
        sale_value = sales_units * selling_price
        if sale_value > 0:
            ar_balance += sale_value
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': sale_value})
            
        current_pipeline = sum(o['qty'] for o in pipeline_orders if o['delivery_day'] > day)
        if (inventory + current_pipeline) <= rop:
            delivery_day = day + lead_time
            pipeline_orders.append({
                'delivery_day': delivery_day, 
                'qty': manual_order_qty, 
                'payment_day': delivery_day + supplier_credit,
                'payable_amount': manual_order_qty * unit_cost
            })
            
        payment_received = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        ar_balance -= payment_received
        payment_made = sum(o['payable_amount'] for o in pipeline_orders if o['payment_day'] == day)
        ap_balance -= payment_made
        
        cash_balance += (payment_received - payment_made)
        history.append({
            "Day": day, "Inventory": inventory, "Outstanding AR": ar_balance,
            "Outstanding AP": ap_balance, "Working Capital": ar_balance + (inventory * unit_cost) - ap_balance,
            "Stockout": stock_out_flag, "Daily Holding Cost": inventory * daily_holding_rate
        })
    return pd.DataFrame(history)

df_res = run_simulation()

# --- Dashboard UI ---
st.title("Inventory Diagnostics & Lifecycle Analysis")

# Row 1: KPIs
k1, k2, k3, k4 = st.columns(4)
avg_inv = df_res['Inventory'].mean()
avg_age = avg_inv / avg_demand
k1.metric("Avg Age of Inventory", f"{avg_age:.1f} Days")
k2.metric("Avg Inventory", f"{avg_inv:.1f} Units")
k3.metric("Avg Working Capital", f"${df_res['Working Capital'].mean():,.1f}")
k4.metric("Stockout Days", f"{df_res['Stockout'].sum()}")

st.divider()

# --- Lifecycle Analysis Interpretation (Reference: Screenshot 2026-05-14 at 8.33.30 AM.png) ---
st.subheader("Cash Flow & Lifecycle Analysis")
st.markdown("**Inventory Lifecycle: Where is the value?**")

# Calculate phases for the chart
days_in_store = avg_age
total_lifecycle = lead_time + days_in_store + customer_credit
cash_to_customer = lead_time + days_in_store
cash_from_customer = total_lifecycle
payment_to_supplier = lead_time + supplier_credit

# Create the Gantt data
lifecycle_data = [
    dict(Task="Physical & Financial Flow", Start=0, Finish=lead_time, Phase="1. In-Transit", Color="#FFA500"),
    dict(Task="Physical & Financial Flow", Start=lead_time, Finish=lead_time + days_in_store, Phase="2. In-Store", Color="#2E8B57"),
    dict(Task="Physical & Financial Flow", Start=lead_time + days_in_store, Finish=total_lifecycle, Phase="3. Receivable", Color="#1E90FF")
]
df_lifecycle = pd.DataFrame(lifecycle_data)

fig_life = px.timeline(df_lifecycle, x_start="Start", x_end="Finish", y="Task", color="Phase",
                       color_discrete_map={"1. In-Transit": "#FFA500", "2. In-Store": "#2E8B57", "3. Receivable": "#1E90FF"},
                       height=300)

# Add Payment and Collection markers
fig_life.add_vline(x=payment_to_supplier, line_dash="dash", line_color="red", 
                   annotation_text=f"PAYMENT TO SUPPLIER (Day {payment_to_supplier:.1f})")
fig_life.add_vline(x=cash_from_customer, line_dash="dot", line_color="yellow", 
                   annotation_text=f"CASH FROM CUSTOMER (Day {cash_from_customer:.1f})", annotation_position="bottom right")

fig_life.update_yaxes(autorange="reversed")
fig_life.update_layout(xaxis_title="Days", showlegend=True)
st.plotly_chart(fig_life, use_container_width=True)

# Interpretation Logic
cash_gap = cash_from_customer - payment_to_supplier
st.info(f"**Interpretation:** Your current Cash Gap is **{cash_gap:.1f} days**. "
        f"{'You are financing your operations for this period.' if cash_gap > 0 else 'Your suppliers are financing your growth.'}")

st.divider()

# --- Visual Analysis ---
st.subheader("Visual Analysis")
fig_inv = px.line(df_res, x="Day", y="Inventory", title="Inventory Levels & ROP", height=500, color_discrete_sequence=['#0047AB'])
fig_inv.add_hline(y=rop, line_dash="dash", line_color="red", annotation_text=f"ROP: {rop}")
st.plotly_chart(fig_inv, use_container_width=True)
