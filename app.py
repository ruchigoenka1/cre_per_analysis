import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(layout="wide", page_title="Full-Width Cash Flow Simulator")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("Control Panel")
    # Button to refresh demand
    if st.button("🔄 Generate New Demand Pattern"):
        st.rerun()
    
    st.subheader("Time & Demand")
    duration = st.number_input("Duration (Days)", value=180)
    avg_demand = st.number_input("Avg. Daily Demand", value=20)
    std_demand = st.number_input("Demand Variability", value=5)
    lead_time = st.number_input("Lead Time (Days)", value=7)
    
    st.subheader("Inventory Policy")
    rop = st.number_input("Reorder Point (Units)", value=150)
    order_qty = st.number_input("Order Quantity (Units)", value=300)
    
    st.subheader("Financials")
    unit_cost = st.number_input("Unit Cost ($)", value=50)
    selling_price = st.number_input("Selling Price ($)", value=90)
    order_cost_fixed = st.number_input("Fixed Ordering Cost ($)", value=150)
    holding_cost_annual = st.number_input("Annual Holding Cost/Unit ($)", value=10.0)
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)

# --- Simulation Logic ---
def run_simulation():
    inventory = int(1.25 * rop)
    cash_balance = 0
    total_holding_costs = 0
    total_ordering_costs = 0
    
    pipeline_orders = [] 
    pending_receivables = [] 
    history = []
    
    daily_holding_rate = holding_cost_annual / 365
    
    for day in range(duration):
        # 1. Demand & Sales
        daily_demand = max(0, int(np.random.normal(avg_demand, std_demand)))
        sales_units = min(inventory, daily_demand)
        stock_out = daily_demand - sales_units
        inventory -= sales_units
        
        # 2. Receivables (Customer Credit)
        revenue_amount = sales_units * selling_price
        if revenue_amount > 0:
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': revenue_amount})
            
        # 3. Handle Arrivals
        for o in list(pipeline_orders):
            if o['delivery_day'] == day:
                inventory += o['qty']
            
        # 4. Ordering (ROP)
        current_pipeline = sum(o['qty'] for o in pipeline_orders if o['delivery_day'] > day)
        if (inventory + current_pipeline) <= rop:
            delivery_day = day + lead_time
            payment_day = delivery_day + supplier_credit
            pipeline_orders.append({
                'delivery_day': delivery_day, 
                'qty': order_qty, 
                'payment_day': payment_day,
                'payable_amount': order_qty * unit_cost
            })
            total_ordering_costs += order_cost_fixed
            
        # 5. Financial Settlement (Trade focus)
        receivable_today = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        payable_today = sum(o['payable_amount'] for o in pipeline_orders if o['payment_day'] == day)
        cash_balance += (receivable_today - payable_today)
        
        # 6. Operational Tracking
        current_day_holding = inventory * daily_holding_rate
        total_holding_costs += current_day_holding
        
        history.append({
            "Day": day,
            "Inventory": inventory,
            "Receivable": receivable_today,
            "Payable": payable_today,
            "Cash_Balance": round(cash_balance, 2),
            "Daily_Holding_Cost": round(current_day_holding, 2),
            "Stockout": 1 if stock_out > 0 else 0
        })
        
    return pd.DataFrame(history), total_holding_costs, total_ordering_costs

df_res, total_hold, total_order = run_simulation()

# --- Main Dashboard ---
st.title("📦 AI Inventory & Cash Flow Auditor")

# KPI Summary
m1, m2, m3, m4 = st.columns(4)
m1.metric("Avg Inventory", f"{int(df_res['Inventory'].mean())} units")
m2.metric("Stock-out Days", f"{df_res['Stockout'].sum()} days")
m3.metric("Total Holding Cost", f"${total_hold:,.2f}")
m4.metric("Total Ordering Cost", f"${total_order:,.2f}")

st.write("") # Padding

# --- Full Width Inventory Graph ---
with st.container():
    st.subheader("Inventory Levels over Time")
    fig_inv = px.line(df_res, x="Day", y="Inventory", 
                      line_shape="hv", 
                      color_discrete_sequence=['#0047AB'],
                      height=400)
    fig_inv.add_hline(y=rop, line_dash="dot", line_color="red", annotation_text="Reorder Point")
    st.plotly_chart(fig_inv, use_container_width=True)

st.write("") # Padding

# --- Full Width Cash Flow Graph ---
with st.container():
    st.subheader("Cumulative Trade Cash Position")
    fig_cash = px.area(df_res, x="Day", y="Cash_Balance", 
                       color_discrete_sequence=['#2E8B57'],
                       height=400)
    st.plotly_chart(fig_cash, use_container_width=True)

# --- Data Log ---
with st.expander("View Daily Simulation Logs"):
    st.dataframe(df_res, use_container_width=True, hide_index=True)
