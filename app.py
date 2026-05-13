import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import math

# Set professional wide layout
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
    std_demand = st.number_input("Demand Variability (Std Dev)", value=5)
    lead_time = st.number_input("Lead Time (Days)", value=7)
    unit_cost = st.number_input("Unit Cost ($)", value=50)
    selling_price = st.number_input("Selling Price ($)", value=90)
    order_cost_fixed = st.number_input("Ordering Cost (per order) ($)", value=150)
    holding_cost_annual = st.number_input("Annual Holding Cost per Unit ($)", value=10.0)
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)
    duration = st.number_input("Simulation Duration (Days)", value=180)

# --- EOQ and Financial Math ---
annual_demand = avg_demand * 365
calculated_eoq = math.sqrt((2 * annual_demand * order_cost_fixed) / holding_cost_annual)

def calc_total_annual_cost(q):
    annual_holding = (q / 2) * holding_cost_annual
    annual_ordering = (annual_demand / q) * order_cost_fixed
    return annual_holding + annual_ordering

cost_current = calc_total_annual_cost(manual_order_qty)
cost_eoq = calc_total_annual_cost(calculated_eoq)
savings = cost_current - cost_eoq

# --- Simulation Engine ---
def run_simulation():
    # Starting balance logic: 1.25 * production trigger (ROP)
    inventory = int(1.25 * rop)
    cash_balance, ar_balance, ap_balance = 0, 0, 0
    pipeline_orders, pending_receivables, history = [], [], []
    daily_holding_rate = holding_cost_annual / 365
    
    for day in range(duration):
        # 1. Demand & Sales
        daily_demand = max(0, int(np.random.normal(avg_demand, std_demand)))
        sales_units = min(inventory, daily_demand)
        stock_out_flag = 1 if daily_demand > sales_units else 0
        inventory -= sales_units
        
        # 2. Book AR (Revenue on sale day)
        sale_value = sales_units * selling_price
        if sale_value > 0:
            ar_balance += sale_value
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': sale_value})
            
        # 3. Handle Arrivals & AP
        for o in list(pipeline_orders):
            if o['delivery_day'] == day:
                inventory += o['qty']
                ap_balance += o['payable_amount']
            
        # 4. Ordering (ROP Trigger)
        current_pipeline = sum(o['qty'] for o in pipeline_orders if o['delivery_day'] > day)
        if (inventory + current_pipeline) <= rop:
            delivery_day = day + lead_time
            payment_day = delivery_day + supplier_credit
            pipeline_orders.append({
                'delivery_day': delivery_day, 
                'qty': manual_order_qty, 
                'payment_day': payment_day,
                'payable_amount': manual_order_qty * unit_cost
            })
            
        # 5. Settlement (Cash Movements)
        payment_received = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        ar_balance -= payment_received
        
        payment_made = sum(o['payable_amount'] for o in pipeline_orders if o['payment_day'] == day)
        ap_balance -= payment_made
        
        cash_balance += (payment_received - payment_made)
        
        # Working Capital Calculation: AR + Inventory Value - AP
        working_capital = ar_balance + (inventory * unit_cost) - ap_balance
        
        history.append({
            "Day": day,
            "Demand": daily_demand,
            "Inventory": inventory,
            "Outstanding AR": ar_balance,
            "Outstanding AP": ap_balance,
            "Working Capital": working_capital,
            "Payment Received": payment_received,
            "Payment Made": payment_made,
            "Cash Balance": cash_balance,
            "Daily Holding Cost": inventory * daily_holding_rate,
            "Stockout": stock_out_flag
        })
        
    return pd.DataFrame(history), len(pipeline_orders) * order_cost_fixed

df_res, total_ordering_cost = run_simulation()
total_holding_cost = df_res['Daily Holding Cost'].sum()

# --- DASHBOARD UI (Reference: Screenshot 2026-05-13 at 5.24.36 PM.jpg) ---
st.title("Inventory Diagnostics & Working Capital Dashboard")

# Row 1: Inventory KPIs
st.subheader("Inventory KPIs")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Stockout Days", f"{df_res['Stockout'].sum()}")
k2.metric("Average Age of Inventory", f"{(df_res['Inventory'].mean() / avg_demand):.1f}")
k3.metric("Average Inventory", f"{df_res['Inventory'].mean():.1f}")
k4.metric("Avg Working Capital", f"{df_res['Working Capital'].mean():.1f}")

# Row 2: Inventory Range
st.subheader("Inventory Range")
r1, r2, r3, r4 = st.columns(4)
r1.metric("Minimum Inventory", f"{df_res['Inventory'].min():.1f}")
r2.metric("Maximum Inventory", f"{df_res['Inventory'].max():.1f}")
r3.metric("Minimum Working Capital", f"{df_res['Working Capital'].min():.1f}")
r4.metric("Maximum Working Capital", f"{df_res['Working Capital'].max():.1f}")

# Row 3: Inventory Cost Metrics
st.subheader("Inventory Cost Metrics")
c1, c2, c3 = st.columns(3)
c1.metric("Total Holding Cost", f"{total_holding_cost:.1f}")
c2.metric("Total Ordering Cost", f"{total_ordering_cost}")
c3.metric("Total Inventory Cost", f"{(total_holding_cost + total_ordering_cost):.1f}")

# Row 4: EOQ
st.subheader("EOQ")
e1, e2 = st.columns(2)
e1.metric("Economic Order Quantity", f"{calculated_eoq:.1f}")
e2.metric("Selected Order Quantity", f"{manual_order_qty}")

# Row 5: Cost Comparison
st.subheader("Cost Comparison")
comp1, comp2, comp3 = st.columns(3)
comp1.metric("Cost with Current Policy", f"{cost_current:.1f}")
comp2.metric("Cost with EOQ", f"{cost_eoq:.1f}")
comp3.metric("Savings Using EOQ", f"{savings:.1f}", delta=f"{savings:.1f}")

st.divider()

# --- Visual Analysis Section (Reference: Screenshot 2026-05-13 at 5.26.10 PM.png) ---
st.subheader("Visual Analysis")

# Inventory Levels with ROP and Stockout Markers
fig_inv = px.line(df_res, x="Day", y="Inventory", title="Inventory Levels", 
                  height=600, color_discrete_sequence=['#0047AB'])
fig_inv.add_hline(y=rop, line_dash="dash", line_color="red", annotation_text=f"ROP: {rop}")

# FIX: Plot stockouts at Y=0 (the bottom) (Reference: Screenshot 2026-05-13 at 5.32.55 PM.png)
stockouts = df_res[df_res['Stockout'] == 1]
if not stockouts.empty:
    fig_inv.add_scatter(x=stockouts["Day"], y=[0] * len(stockouts), mode="markers", 
                        name="Stockout", marker=dict(color="red", size=12, symbol="x-thin"))

st.plotly_chart(fig_inv, use_container_width=True)

# Working Capital Trend
fig_wc = px.area(df_res, x="Day", y="Working Capital", title="Working Capital Trend", 
                 height=400, color_discrete_sequence=['#2E8B57'])
st.plotly_chart(fig_wc, use_container_width=True)

# Cash Balance Trend
fig_cash = px.line(df_res, x="Day", y="Cash Balance", title="Cumulative Cash Flow (Trade Balance)", 
                   height=400, color_discrete_sequence=['#FF8C00'])
st.plotly_chart(fig_cash, use_container_width=True)

# --- Ledger View ---
with st.expander("Detailed Daily Transaction Ledger"):
    st.dataframe(df_res, use_container_width=True, hide_index=True)
