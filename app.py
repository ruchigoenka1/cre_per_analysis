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
    # Annual percentage based on user summary preference
    holding_cost_pct = st.number_input("Annual Holding Cost (%)", value=20.0) / 100
    opp_cost_pct = st.number_input("Cost of Capital / Interest (%)", value=12.0) / 100
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)
    duration = st.number_input("Simulation Duration (Days)", value=180)

# --- Financial & EOQ Math ---
annual_demand = avg_demand * 365
h_physical = unit_cost * holding_cost_pct
# Physical EOQ based on standard storage costs
eoq_physical = math.sqrt((2 * annual_demand * order_cost_fixed) / h_physical)

# Financial EOQ adjusted for trade credit gap
daily_interest_rate = opp_cost_pct / 365
credit_gap_days = customer_credit - supplier_credit
credit_impact_per_unit = unit_cost * (daily_interest_rate * credit_gap_days * 365)
h_financial = max(0.01, h_physical + (unit_cost * opp_cost_pct) + credit_impact_per_unit)
eoq_financial = math.sqrt((2 * annual_demand * order_cost_fixed) / h_financial)

# Cost comparison logic
def calc_total_annual_cost(q, h_val):
    annual_holding = (q / 2) * h_val
    annual_ordering = (annual_demand / q) * order_cost_fixed
    return annual_holding + annual_ordering

cost_current = calc_total_annual_cost(manual_order_qty, h_physical)
cost_eoq = calc_total_annual_cost(eoq_physical, h_physical)
savings = cost_current - cost_eoq

# --- Simulation Engine ---
def run_simulation():
    # Starting balance logic: 1.25 * production trigger
    inventory = int(1.25 * rop)
    cash_balance, ar_balance, ap_balance = 0, 0, 0
    pipeline_orders, pending_receivables, history = [], [], []
    daily_holding_rate = h_physical / 365
    
    for day in range(duration):
        # 1. MORNING: Shipments arrive first (User assumption)
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
            pipeline_orders.append({
                'delivery_day': delivery_day, 
                'qty': manual_order_qty, 
                'payment_day': delivery_day + supplier_credit,
                'payable_amount': manual_order_qty * unit_cost
            })
            
        # 5. Settlement (Cash Movements)
        payment_received = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        ar_balance -= payment_received
        payment_made = sum(o['payable_amount'] for o in pipeline_orders if o['payment_day'] == day)
        ap_balance -= payment_made
        cash_balance += (payment_received - payment_made)
        
        # Financial Health Metrics
        inv_working_capital = inventory * unit_cost
        net_working_capital = ar_balance + inv_working_capital - ap_balance
        
        history.append({
            "Day": day, "Demand": daily_demand, "Inventory": inventory,
            "Outstanding AR": ar_balance, "Outstanding AP": ap_balance,
            "Net Working Capital": net_working_capital,
            "Inventory Working Capital": inv_working_capital,
            "Payment Received": payment_received, "Payment Made": payment_made,
            "Cash Balance": cash_balance, "Daily Holding Cost": inventory * daily_holding_rate,
            "Stockout": stock_out_flag
        })
        
    return pd.DataFrame(history), len(pipeline_orders) * order_cost_fixed

df_res, total_ordering_cost = run_simulation()
total_holding_cost = df_res['Daily Holding Cost'].sum()

# --- DASHBOARD UI (Reference: Screenshot 2026-05-13 at 5.24.36 PM.jpg & 6.14.09 PM.png) ---
st.title("Inventory Diagnostics & Working Capital Dashboard")

# Row 1: Inventory KPIs
st.subheader("Inventory KPIs")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Stockout Days", f"{df_res['Stockout'].sum()}")
avg_age = (df_res['Inventory'].mean() / avg_demand)
k2.metric("Average Age of Inventory", f"{avg_age:.1f}")
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

# Row 3: EOQ & Savings Analysis
st.subheader("EOQ and Savings Analysis")
e1, e2, e3, e4 = st.columns(4)
e1.metric("Physical EOQ", f"{int(eoq_physical)}")
e2.metric("Financial EOQ", f"{int(eoq_financial)}")
e3.metric("Annual Savings (EOQ)", f"${savings:,.1f}", delta=f"${savings:,.1f}")
e4.metric("Net Credit Gap", f"{credit_gap_days} Days", delta=credit_gap_days, delta_color="inverse")

st.divider()

# --- Cash Flow & Lifecycle Analysis (Reference: Screenshot 2026-05-14 at 8.33.30 AM.png) ---
st.subheader("Cash Flow & Lifecycle Analysis")
st.markdown("**Inventory Lifecycle: Where is the value?**")

days_in_store = avg_age
total_lifecycle = lead_time + days_in_store + customer_credit
payment_to_supplier = lead_time + supplier_credit

lifecycle_data = [
    dict(Task="Physical & Financial Flow", Start=0, Finish=lead_time, Phase="1. In-Transit"),
    dict(Task="Physical & Financial Flow", Start=lead_time, Finish=lead_time + days_in_store, Phase="2. In-Store"),
    dict(Task="Physical & Financial Flow", Start=lead_time + days_in_store, Finish=total_lifecycle, Phase="3. Receivable")
]
fig_life = px.timeline(pd.DataFrame(lifecycle_data), x_start="Start", x_end="Finish", y="Task", color="Phase",
                       color_discrete_map={"1. In-Transit": "#FFA500", "2. In-Store": "#2E8B57", "3. Receivable": "#1E90FF"},
                       height=300)

fig_life.add_vline(x=payment_to_supplier, line_dash="dash", line_color="red", 
                   annotation_text=f"PAYMENT TO SUPPLIER (Day {payment_to_supplier:.1f})")
fig_life.add_vline(x=total_lifecycle, line_dash="dot", line_color="yellow", 
                   annotation_text=f"CASH FROM CUSTOMER (Day {total_lifecycle:.1f})", annotation_position="bottom right")
fig_life.update_yaxes(autorange="reversed")
st.plotly_chart(fig_life, use_container_width=True)

cash_gap = total_lifecycle - payment_to_supplier
st.info(f"**Interpretation:** Your current Cash Gap is **{cash_gap:.1f} days**. "
        f"{'You are self-financing during this period.' if cash_gap > 0 else 'Suppliers are effectively financing your growth.'}")

st.divider()

# --- Visual Analysis (Reference: Screenshot 2026-05-13 at 5.26.10 PM.png & 5.32.55 PM.png) ---
st.subheader("Visual Analysis")
fig_inv = px.line(df_res, x="Day", y="Inventory", title="Inventory Levels with ROP and Stockout Indicators", 
                  height=600, color_discrete_sequence=['#0047AB'])
fig_inv.add_hline(y=rop, line_dash="dash", line_color="red", annotation_text=f"ROP: {rop}")

stockouts = df_res[df_res['Stockout'] == 1]
if not stockouts.empty:
    # Plot markers slightly above zero for visibility
    fig_inv.add_scatter(x=stockouts["Day"], y=[5] * len(stockouts), mode="markers", 
                        name="Stockout Event", marker=dict(color="red", size=15, symbol="x"))

st.plotly_chart(fig_inv, use_container_width=True)

with st.expander("Detailed Daily Transaction Ledger"):
    st.dataframe(df_res, use_container_width=True, hide_index=True)
