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
    holding_cost_pct = st.number_input("Annual Holding Cost (%)", value=20.0) / 100
    opp_cost_pct = st.number_input("Cost of Capital / Interest (%)", value=12.0) / 100
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)
    duration = st.number_input("Simulation Duration (Days)", value=180)

# --- Advanced EOQ Calculations ---
annual_demand = avg_demand * 365
# 1. Physical Holding Cost
h_physical = unit_cost * holding_cost_pct
eoq_physical = math.sqrt((2 * annual_demand * order_cost_fixed) / h_physical)

# 2. Financial/Credit-Adjusted EOQ
daily_interest_rate = opp_cost_pct / 365
credit_gap_days = customer_credit - supplier_credit
credit_impact_per_unit = unit_cost * (daily_interest_rate * credit_gap_days * 365)
h_financial = h_physical + (unit_cost * opp_cost_pct) + credit_impact_per_unit
h_financial = max(h_financial, 0.01) # Prevent division by zero
eoq_financial = math.sqrt((2 * annual_demand * order_cost_fixed) / h_financial)

# --- Cost Comparison Logic ---
def calc_total_annual_cost(q, h_val):
    annual_holding = (q / 2) * h_val
    annual_ordering = (annual_demand / q) * order_cost_fixed
    return annual_holding + annual_ordering

cost_current = calc_total_annual_cost(manual_order_qty, h_physical)
cost_eoq = calc_total_annual_cost(eoq_physical, h_physical)
savings = cost_current - cost_eoq

# --- Simulation Engine ---
def run_simulation():
    inventory = int(1.25 * rop)
    cash_balance, ar_balance, ap_balance = 0, 0, 0
    pipeline_orders, pending_receivables, history = [], [], []
    daily_holding_rate = h_physical / 365
    
    for day in range(duration):
        # 1. MORNING: Shipments arrive (Assumed at start of day)
        for o in list(pipeline_orders):
            if o['delivery_day'] == day:
                inventory += o['qty']
                ap_balance += o['payable_amount']
        
        # 2. DURING DAY: Demand occurs
        daily_demand = max(0, int(np.random.normal(avg_demand, std_demand)))
        sales_units = min(inventory, daily_demand)
        # Stockout check after morning arrivals
        stock_out_flag = 1 if daily_demand > (inventory + (daily_demand - sales_units)) else 0
        inventory -= sales_units
        
        # 3. Book AR (Accrual)
        sale_value = sales_units * selling_price
        if sale_value > 0:
            ar_balance += sale_value
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': sale_value})
            
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
        
        # Financial Health Metrics
        inventory_working_capital = inventory * unit_cost
        net_working_capital = ar_balance + inventory_working_capital - ap_balance
        
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

# --- DASHBOARD UI ---
st.title("Inventory Diagnostics & Working Capital Dashboard")

# Row 1: Inventory KPIs
st.subheader("Inventory KPIs")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Stockout Days", f"{df_res['Stockout'].sum()}")
k2.metric("Average Age of Inventory", f"{(df_res['Inventory'].mean() / avg_demand):.1f}")
k3.metric("Average Inventory", f"{df_res['Inventory'].mean():.1f}")
k4.metric("Avg Net Working Capital", f"${df_res['Net Working Capital'].mean():,.1f}")
k5.metric("Avg Inv Working Capital", f"${df_res['Inventory Working Capital'].mean():,.1f}")

# Row 2: Trade Credit Metrics
st.subheader("Trade Credit Metrics")
a1, a2, a3, a4 = st.columns(4)
a1.metric("Avg Outstanding AR", f"${df_res['Outstanding AR'].mean():,.1f}")
a2.metric("Peak AR Exposure", f"${df_res['Outstanding AR'].max():,.1f}")
a3.metric("Avg Outstanding AP", f"${df_res['Outstanding AP'].mean():,.1f}")
a4.metric("Peak AP Balance", f"${df_res['Outstanding AP'].max():,.1f}")

# Row 3: Inventory Range & Costs
st.subheader("Inventory Range & Costs")
r1, r2, r3, r4 = st.columns(4)
r1.metric("Min Inventory", f"{df_res['Inventory'].min():.1f}")
r2.metric("Max Inventory", f"{df_res['Inventory'].max():.1f}")
r3.metric("Total Holding Cost", f"${total_holding_cost:,.0f}")
r4.metric("Total Ordering Cost", f"${total_ordering_cost:,.0f}")

# Row 4: EOQ & Financial Savings
st.subheader("EOQ and Savings Analysis")
e1, e2, e3, e4 = st.columns(4)
e1.metric("Physical EOQ", f"{int(eoq_physical)}")
e2.metric("Financial EOQ", f"{int(eoq_financial)}")
e3.metric("Annual Savings (EOQ)", f"${savings:,.1f}", delta=f"${savings:,.1f}")
e4.metric("Net Credit Gap", f"{credit_gap_days} Days", delta=credit_gap_days, delta_color="inverse")

st.divider()

# --- Visual Analysis ---
st.subheader("Visual Analysis")

# Inventory Levels
fig_inv = px.line(df_res, x="Day", y="Inventory", title="Inventory Levels with ROP and Stockout Indicators", 
                  height=600, color_discrete_sequence=['#0047AB'])
fig_inv.add_hline(y=rop, line_dash="dash", line_color="red", annotation_text=f"ROP: {rop}")

# Add Stockout markers at the bottom for visibility
stockouts = df_res[df_res['Stockout'] == 1]
if not stockouts.empty:
    fig_inv.add_scatter(x=stockouts["Day"], y=[5] * len(stockouts), mode="markers", 
                        name="Stockout Event", marker=dict(color="red", size=15, symbol="x"))
st.plotly_chart(fig_inv, use_container_width=True)

# Working Capital Trend
st.plotly_chart(px.area(df_res, x="Day", y="Net Working Capital", title="Net Working Capital Trend", 
                        height=400, color_discrete_sequence=['#2E8B57']), use_container_width=True)

# Detailed Ledger
with st.expander("Detailed Daily Transaction Ledger"):
    st.dataframe(df_res, use_container_width=True, hide_index=True)
