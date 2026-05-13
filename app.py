import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import math

st.set_page_config(layout="wide", page_title="Inventory KPI Auditor")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("Simulation Settings")
    if st.button("🔄 Run New Simulation"):
        st.rerun()
    
    st.subheader("Inventory Policy")
    rop = st.number_input("Reorder Point", value=150)
    manual_order_qty = st.number_input("Selected Order Quantity", value=300)
    
    st.subheader("Cost & Demand")
    avg_demand = st.number_input("Avg. Daily Demand", value=20)
    std_demand = st.number_input("Demand Variability", value=5)
    lead_time = st.number_input("Lead Time (Days)", value=7)
    unit_cost = st.number_input("Unit Cost ($)", value=50)
    order_cost_fixed = st.number_input("Ordering Cost ($)", value=150)
    holding_cost_annual = st.number_input("Annual Holding Cost/Unit ($)", value=10.0)
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)
    selling_price = st.number_input("Selling Price ($)", value=90)
    duration = 180

# --- Calculations ---
annual_demand = avg_demand * 365
# EOQ Calculation
eoq = math.sqrt((2 * annual_demand * order_cost_fixed) / holding_cost_annual)

# Cost Comparison Logic
def calc_total_cost(q):
    annual_holding = (q / 2) * holding_cost_annual
    annual_ordering = (annual_demand / q) * order_cost_fixed
    return annual_holding + annual_ordering

cost_current = calc_total_cost(manual_order_qty)
cost_eoq = calc_total_cost(eoq)
savings = cost_current - cost_eoq

# --- Simulation Engine ---
def run_simulation():
    inventory = int(1.25 * rop)
    cash_balance, ar_balance, ap_balance = 0, 0, 0
    pipeline_orders, pending_receivables, history = [], [], []
    daily_holding_rate = holding_cost_annual / 365
    
    for day in range(duration):
        daily_demand = max(0, int(np.random.normal(avg_demand, std_demand)))
        sales_units = min(inventory, daily_demand)
        inventory -= sales_units
        
        # AR & Cash In
        sale_value = sales_units * selling_price
        if sale_value > 0:
            ar_balance += sale_value
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': sale_value})
        
        payment_received = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        ar_balance -= payment_received
        
        # Deliveries & AP
        for o in list(pipeline_orders):
            if o['delivery_day'] == day:
                inventory += o['qty']
                ap_balance += o['payable_amount']
        
        # Ordering
        current_pipeline = sum(o['qty'] for o in pipeline_orders if o['delivery_day'] > day)
        if (inventory + current_pipeline) <= rop:
            pipeline_orders.append({
                'delivery_day': day + lead_time, 
                'qty': manual_order_qty, 
                'payment_day': day + lead_time + supplier_credit,
                'payable_amount': manual_order_qty * unit_cost
            })
            
        # AP & Cash Out
        payment_made = sum(o['payable_amount'] for o in pipeline_orders if o['payment_day'] == day)
        ap_balance -= payment_made
        
        cash_balance += (payment_received - payment_made)
        working_capital = ar_balance + (inventory * unit_cost) - ap_balance
        
        history.append({
            "Day": day,
            "Inventory": inventory,
            "Working_Capital": working_capital,
            "Stockout": 1 if daily_demand > sales_units else 0,
            "Daily_Hold": inventory * daily_holding_rate
        })
        
    return pd.DataFrame(history), len([o for o in pipeline_orders]) * order_cost_fixed

df_res, total_ordering_cost = run_simulation()
total_holding_cost = df_res['Daily_Hold'].sum()

# --- KPI Section (Modeled after Screenshot 2026-05-13 at 5.24.36 PM.jpg) ---
st.title("Inventory Diagnostics Dashboard")

# Row 1: Inventory KPIs
st.subheader("Inventory KPIs")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Stockout Days", f"{df_res['Stockout'].sum()}")
# Avg Age = Avg Inventory / Avg Daily Demand
avg_inv = df_res['Inventory'].mean()
k2.metric("Average Age of Inventory", f"{(avg_inv / avg_demand):.1f}")
k3.metric("Average Inventory", f"{avg_inv:.1f}")
k4.metric("Avg Working Capital", f"{df_res['Working_Capital'].mean():.1f}")

# Row 2: Inventory Range
st.subheader("Inventory Range")
r1, r2, r3, r4 = st.columns(4)
r1.metric("Minimum Inventory", f"{df_res['Inventory'].min():.1f}")
r2.metric("Maximum Inventory", f"{df_res['Inventory'].max():.1f}")
r3.metric("Minimum Working Capital", f"{df_res['Working_Capital'].min():.1f}")
r4.metric("Maximum Working Capital", f"{df_res['Working_Capital'].max():.1f}")

# Row 3: Inventory Cost Metrics
st.subheader("Inventory Cost Metrics")
c1, c2, c3 = st.columns(3)
c1.metric("Total Holding Cost", f"{total_holding_cost:.1f}")
c2.metric("Total Ordering Cost", f"{total_ordering_cost}")
c3.metric("Total Inventory Cost", f"{(total_holding_cost + total_ordering_cost):.1f}")

# Row 4: EOQ
st.subheader("EOQ")
e1, e2 = st.columns(2)
e1.metric("Economic Order Quantity", f"{eoq:.1f}")
e2.metric("Selected Order Quantity", f"{manual_order_qty}")

# Row 5: Cost Comparison
st.subheader("Cost Comparison")
comp1, comp2, comp3 = st.columns(3)
comp1.metric("Cost with Current Policy", f"{cost_current:.1f}")
comp2.metric("Cost with EOQ", f"{cost_eoq:.1f}")
comp3.metric("Savings Using EOQ", f"{savings:.1f}", delta=f"{savings:.1f}")

st.divider()

# Charts
st.subheader("Visual Analysis")
st.plotly_chart(px.line(df_res, x="Day", y="Inventory", title="Inventory Levels", height=300), use_container_width=True)
st.plotly_chart(px.area(df_res, x="Day", y="Working_Capital", title="Working Capital Trend", height=300), use_container_width=True)
