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
    std_demand = st.number_input("Demand Variability (Std Dev)", value=5)
    lead_time = st.number_input("Lead Time (Days)", value=7)
    unit_cost = st.number_input("Unit Cost ($)", value=50)
    selling_price = st.number_input("Selling Price ($)", value=90)
    order_cost_fixed = st.number_input("Ordering Cost ($)", value=150)
    holding_cost_pct = st.number_input("Annual Holding Cost (%)", value=20.0) / 100
    opp_cost_pct = st.number_input("Cost of Capital / Interest (%)", value=12.0) / 100
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)
    duration = st.number_input("Simulation Duration (Days)", value=180)

# --- Financial & EOQ Math ---
annual_demand = avg_demand * 365
h_physical = unit_cost * holding_cost_pct
eoq_physical = math.sqrt((2 * annual_demand * order_cost_fixed) / h_physical)

daily_interest_rate = opp_cost_pct / 365
credit_gap_days = customer_credit - supplier_credit
credit_impact_per_unit = unit_cost * (daily_interest_rate * credit_gap_days * 365)
h_financial = max(0.01, h_physical + (unit_cost * opp_cost_pct) + credit_impact_per_unit)
eoq_financial = math.sqrt((2 * annual_demand * order_cost_fixed) / h_financial)

def calc_total_annual_cost(q, h_val):
    return ((q / 2) * h_val) + ((annual_demand / q) * order_cost_fixed)

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
        # 1. MORNING: Shipments arrive first
        for o in list(pipeline_orders):
            if o['delivery_day'] == day:
                inventory += o['qty']
                ap_balance += o['payable_amount']
        
        # 2. DURING DAY: Demand occurs
        daily_demand = max(0, int(np.random.normal(avg_demand, std_demand)))
        sales_units = min(inventory, daily_demand)
        stock_out_flag = 1 if daily_demand > (inventory + (daily_demand - sales_units)) else 0
        inventory -= sales_units
        
        # 3. Book AR
        sale_value = sales_units * selling_price
        if sale_value > 0:
            ar_balance += sale_value
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': sale_value})
            
        # 4. Ordering (ROP Trigger)
        current_pipeline = sum(o['qty'] for o in pipeline_orders if o['delivery_day'] > day)
        if (inventory + current_pipeline) <= rop:
            delivery_day = day + lead_time
            pipeline_orders.append({
                'delivery_day': delivery_day, 
                'qty': manual_order_qty, 
                'payment_day': delivery_day + supplier_credit,
                'payable_amount': manual_order_qty * unit_cost
            })
            
        # 5. Settlement
        pay_received = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        ar_balance -= pay_received
        pay_made = sum(o['payable_amount'] for o in pipeline_orders if o['payment_day'] == day)
        ap_balance -= pay_made
        cash_balance += (pay_received - pay_made)
        
        # Financial Health Metrics
        inv_wc = inventory * unit_cost
        history.append({
            "Day": day, "Demand": daily_demand, "Inventory": inventory,
            "Outstanding AR": ar_balance, "Outstanding AP": ap_balance,
            "Net Working Capital": ar_balance + inv_wc - ap_balance,
            "Inventory Working Capital": inv_wc, "Cash Balance": cash_balance, "Stockout": stock_out_flag,
            "Daily Holding Cost": inventory * daily_holding_rate
        })
    return pd.DataFrame(history), len(pipeline_orders) * order_cost_fixed

df_res, total_ordering_cost = run_simulation()

# --- DASHBOARD UI ---
st.title("Inventory Diagnostics & Lifecycle Analysis")

# Row 1: Primary Inventory KPIs
st.subheader("Inventory & Trade Credit KPIs")
k1, k2, k3, k4, k5 = st.columns(5)
avg_age = (df_res['Inventory'].mean() / avg_demand)
k1.metric("Stockout Days", f"{df_res['Stockout'].sum()}")
k2.metric("Avg Age of Inventory", f"{avg_age:.1f} Days")
k3.metric("Avg Net Working Capital", f"${df_res['Net Working Capital'].mean():,.1f}")
k4.metric("Avg AR Balance", f"${df_res['Outstanding AR'].mean():,.1f}")
k5.metric("Avg AP Balance", f"${df_res['Outstanding AP'].mean():,.1f}")

# Row 2: EOQ & Costs
st.subheader("EOQ & Savings Analysis")
e1, e2, e3, e4 = st.columns(4)
e1.metric("Physical EOQ", f"{int(eoq_physical)}")
e2.metric("Financial EOQ", f"{int(eoq_financial)}")
e3.metric("Net Credit Gap", f"{credit_gap_days} Days", delta=credit_gap_days, delta_color="inverse")
e4.metric("Annual Savings (EOQ)", f"${savings:,.1f}", delta=f"${savings:,.1f}")

st.divider()

# --- Horizontal Lifecycle Analysis ---
st.subheader("Cash Flow & Lifecycle Analysis")
st.markdown("**Inventory Lifecycle: Where is the value?**")

days_in_store = avg_age
total_lifecycle = lead_time + days_in_store + customer_credit
pay_supplier = lead_time + supplier_credit

# Fixed Bar chart to avoid datetime errors
fig_life = go.Figure()
fig_life.add_trace(go.Bar(y=["Flow"], x=[lead_time], name="1. In-Transit", orientation='h', marker_color="#FFA500"))
fig_life.add_trace(go.Bar(y=["Flow"], x=[days_in_store], name="2. In-Store", orientation='h', marker_color="#2E8B57"))
fig_life.add_trace(go.Bar(y=["Flow"], x=[customer_credit], name="3. Receivable", orientation='h', marker_color="#1E90FF"))

fig_life.update_layout(barmode='stack', height=300, showlegend=True, xaxis_title="Days", yaxis_visible=False)
fig_life.add_vline(x=pay_supplier, line_dash="dash", line_color="red", annotation_text=f"PAYMENT TO SUPPLIER (Day {pay_supplier:.1f})")
fig_life.add_vline(x=total_lifecycle, line_dash="dot", line_color="yellow", annotation_text=f"CASH FROM CUSTOMER (Day {total_lifecycle:.1f})")
st.plotly_chart(fig_life, use_container_width=True)

cash_gap = total_lifecycle - pay_supplier
st.info(f"**Interpretation:** Your current Cash Gap is **{cash_gap:.1f} days**. {'Suppliers are effectively financing your growth.' if cash_gap < 0 else 'You are self-financing your operations.'}")

st.divider()

# --- Visual Analysis Section ---
st.subheader("Visual Analysis")

# Inventory Levels
fig_inv = px.line(df_res, x="Day", y="Inventory", title="Inventory Levels & ROP", height=500, color_discrete_sequence=['#0047AB'])
fig_inv.add_hline(y=rop, line_dash="dash", line_color="red", annotation_text=f"ROP: {rop}")
# Stockout markers at the bottom for visibility
stockouts = df_res[df_res['Stockout'] == 1]
if not stockouts.empty:
    fig_inv.add_scatter(x=stockouts["Day"], y=[5] * len(stockouts), mode="markers", name="Stockout", marker=dict(color="red", size=12, symbol="x"))
st.plotly_chart(fig_inv, use_container_width=True)

# Working Capital Trend
fig_wc = px.area(df_res, x="Day", y="Net Working Capital", title="Net Working Capital Trend (AR + Inventory - AP)", height=400, color_discrete_sequence=['#2E8B57'])
st.plotly_chart(fig_wc, use_container_width=True)

with st.expander("Detailed Daily Transaction Ledger"):
    st.dataframe(df_res, use_container_width=True, hide_index=True)
