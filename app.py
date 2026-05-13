import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
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
    std_demand = st.number_input("Demand Variability (Std Dev)", value=5)
    lead_time = st.number_input("Lead Time (Days)", value=7)
    unit_cost = st.number_input("Unit Cost ($)", value=50)
    selling_price = st.number_input("Selling Price ($)", value=90)
    order_cost_fixed = st.number_input("Ordering Cost (per order) ($)", value=150)
    # Applied as an annual percentage
    holding_cost_pct = st.number_input("Annual Holding Cost (%)", value=20.0) / 100
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)
    duration = st.number_input("Simulation Duration (Days)", value=180)

# --- Financial & EOQ Math ---
annual_demand = avg_demand * 365
# Holding cost per unit per year for EOQ formula
h_cost_per_unit = unit_cost * holding_cost_pct

calculated_eoq = math.sqrt((2 * annual_demand * order_cost_fixed) / h_cost_per_unit)

def calc_total_annual_cost(q):
    annual_holding = (q / 2) * h_cost_per_unit
    annual_ordering = (annual_demand / q) * order_cost_fixed
    return annual_holding + annual_ordering

cost_current = calc_total_annual_cost(manual_order_qty)
cost_eoq = calc_total_annual_cost(calculated_eoq)
savings = cost_current - cost_eoq

# --- Simulation Engine ---
def run_simulation():
    # Initial balance at 1.25 * production trigger (ROP)
    inventory = int(1.25 * rop)
    cash_balance, ar_balance, ap_balance = 0, 0, 0
    pipeline_orders, pending_receivables, history = [], [], []
    daily_holding_rate = h_cost_per_unit / 365
    
    for day in range(duration):
        # 1. MORNING: Shipments arrive first
        for o in list(pipeline_orders):
            if o['delivery_day'] == day:
                inventory += o['qty']
                ap_balance += o['payable_amount']
        
        # 2. DURING DAY: Demand occurs
        daily_demand = max(0, int(np.random.normal(avg_demand, std_demand)))
        
        # 3. Fulfillment & Stockout Logic
        sales_units = min(inventory, daily_demand)
        # Stockout occurs if demand exceeds available inventory after arrivals
        stock_out_flag = 1 if daily_demand > (inventory + sales_units) else 0
        inventory -= sales_units
        
        # 4. Book Accounts Receivable (Accrual)
        sale_value = sales_units * selling_price
        if sale_value > 0:
            ar_balance += sale_value
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': sale_value})
            
        # 5. Ordering (Reorder Point Trigger)
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
            
        # 6. Financial Settlement (Cash In/Out)
        payment_received = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        ar_balance -= payment_received
        
        payment_made = sum(o['payable_amount'] for o in pipeline_orders if o['payment_day'] == day)
        ap_balance -= payment_made
        
        cash_balance += (payment_received - payment_made)
        
        # Financial Health Metrics
        net_working_capital = ar_balance + (inventory * unit_cost) - ap_balance
        inventory_working_capital = inventory * unit_cost
        
        history.append({
            "Day": day,
            "Demand": daily_demand,
            "Inventory": inventory,
            "Outstanding AR": ar_balance,
            "Outstanding AP": ap_balance,
            "Net Working Capital": net_working_capital,
            "Inventory Working Capital": inventory_working_capital,
            "Payment Received": payment_received,
            "Payment Made": payment_made,
            "Cash Balance": cash_balance,
            "Daily Holding Cost": inventory * daily_holding_rate,
            "Stockout": stock_out_flag
        })
        
    return pd.DataFrame(history), len(pipeline_orders) * order_cost_fixed

df_res, total_ordering_cost = run_simulation()
total_holding_cost = df_res['Daily Holding Cost'].sum()

# --- DASHBOARD UI (Reference: Screenshot 2026-05-13 at 6.14.09 PM.png) ---
st.title("Inventory Diagnostics & Working Capital Dashboard")

# Row 1: Inventory KPIs
st.subheader("Inventory KPIs")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Stockout Days", f"{df_res['Stockout'].sum()}")
k2.metric("Average Age of Inventory", f"{(df_res['Inventory'].mean() / avg_demand):.1f}")
k3.metric("Average Inventory", f"{df_res['Inventory'].mean():.1f}")
k4.metric("Avg Working Capital", f"{df_res['Net Working Capital'].mean():.1f}")
k5.metric("Avg Inventory Working Capital", f"${df_res['Inventory Working Capital'].mean():,.1f}")

# Row 2: Inventory Range
st.subheader("Inventory Range")
r1, r2, r3, r4 = st.columns(4)
r1.metric("Minimum Inventory", f"{df_res['Inventory'].min():.1f}")
r2.metric("Maximum Inventory", f"{df_res['Inventory'].max():.1f}")
r3.metric("Minimum Working Capital", f"{df_res['Net Working Capital'].min():.1f}")
r4.metric("Maximum Working Capital", f"{df_res['Net Working Capital'].max():.1f}")

# Row 3: Inventory Cost Metrics
st.subheader("Inventory Cost Metrics")
c1, c2, c3 = st.columns(3)
c1.metric("Total Holding Cost", f"{total_holding_cost:.1f}")
c2.metric("Total Ordering Cost", f"{total_ordering_cost}")
c3.metric("Total Inventory Cost", f"{(total_holding_cost + total_ordering_cost):.1f}")

# Row 4: EOQ & Cost Comparison
st.subheader("EOQ and Savings Analysis")
e1, e2, e3 = st.columns(3)
e1.metric("Economic Order Quantity", f"{calculated_eoq:.1f}")
e2.metric("Cost with EOQ", f"${cost_eoq:,.1f}")
e3.metric("Savings Using EOQ", f"${savings:,.1f}", delta=f"{savings:,.1f}")

st.divider()

# --- Visual Analysis (Reference: Screenshot 2026-05-13 at 5.26.10 PM.png) ---
st.subheader("Visual Analysis")

# Inventory Levels Graph
fig_inv = px.line(df_res, x="Day", y="Inventory", title="Inventory Levels with ROP and Stockout Indicators", 
                  height=600, color_discrete_sequence=['#0047AB'])
fig_inv.add_hline(y=rop, line_dash="dash", line_color="red", annotation_text=f"ROP: {rop}")

# Add Stockout markers at the bottom
stockouts = df_res[df_res['Stockout'] == 1]
if not stockouts.empty:
    fig_inv.add_scatter(x=stockouts["Day"], y=stockouts["Inventory"], mode="markers", 
                        name="Stockout Event", marker=dict(color="red", size=12, symbol="x"))

st.plotly_chart(fig_inv, use_container_width=True)

# Net Working Capital Trend
fig_wc = px.area(df_res, x="Day", y="Net Working Capital", title="Net Working Capital Trend (AR + Inventory - AP)", 
                 height=400, color_discrete_sequence=['#2E8B57'])
st.plotly_chart(fig_wc, use_container_width=True)

# Ledger view for professional auditing
with st.expander("Detailed Daily Transaction Ledger"):
    st.dataframe(df_res, use_container_width=True, hide_index=True)
