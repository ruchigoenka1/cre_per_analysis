import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(layout="wide", page_title="Trade Credit & Inventory Simulator")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("Simulation Settings")
    duration = st.number_input("Duration (Days)", value=180)
    
    st.subheader("Inventory Policy")
    rop = st.number_input("Reorder Point (Units)", value=150)
    order_qty = st.number_input("Order Quantity (Units)", value=300)
    
    st.subheader("Demand & Lead Time")
    avg_demand = st.number_input("Avg. Daily Demand", value=20)
    std_demand = st.number_input("Demand Variability", value=5)
    lead_time = st.number_input("Lead Time (Days)", value=7)
    
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
    # Initial setup
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
        
        # 2. Track Receivables (Revenue is recognized on payment_day)
        revenue_amount = sales_units * selling_price
        if revenue_amount > 0:
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': revenue_amount})
            
        # 3. Handle Inventory Arrivals
        for o in list(pipeline_orders):
            if o['delivery_day'] == day:
                inventory += o['qty']
            
        # 4. Ordering Logic (ROP)
        current_pipeline = sum(o['qty'] for o in pipeline_orders if o['delivery_day'] > day)
        if (inventory + current_pipeline) <= rop:
            delivery_day = day + lead_time
            payment_day = delivery_day + supplier_credit
            cost_of_goods = order_qty * unit_cost
            
            pipeline_orders.append({
                'delivery_day': delivery_day, 
                'qty': order_qty, 
                'payment_day': payment_day,
                'payable_amount': cost_of_goods
            })
            total_ordering_costs += order_cost_fixed
            
        # 5. Financial Settlement
        # Receivables: Money entering the cash balance today
        receivable_today = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        
        # Payables: Money exiting the cash balance today
        payable_today = sum(o['payable_amount'] for o in pipeline_orders if o['payment_day'] == day)
        
        # Update Cash Balance (Excluding holding/ordering costs as requested)
        cash_balance += (receivable_today - payable_today)
        
        # Update Cumulative Holding Cost (Tracked separately)
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

# --- Dashboard ---
st.title("🚜 Inventory & Trade Cash Flow Simulation")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Avg Inventory", f"{int(df_res['Inventory'].mean())} units")
c2.metric("Stock-out Days", f"{df_res['Stockout'].sum()} days")
c3.metric("Total Holding Cost", f"${total_hold:,.2f}")
c4.metric("Total Ordering Cost", f"${total_order:,.2f}")

# --- Visualization ---
st.subheader("Inventory Levels & Net Cash Position")
# Using a dual-axis style chart or side-by-side
fig = px.line(df_res, x="Day", y=["Inventory", "Cash_Balance"], 
              labels={"value": "Level / Amount", "variable": "Metric"},
              color_discrete_map={"Inventory": "#0047AB", "Cash_Balance": "#2E8B57"})
st.plotly_chart(fig, use_container_width=True)

# --- Data Table ---
st.subheader("📋 Daily Simulation Logs")
# Formatting the table for clarity
st.dataframe(
    df_res[["Day", "Inventory", "Receivable", "Payable", "Cash_Balance", "Daily_Holding_Cost", "Stockout"]], 
    use_container_width=True, 
    hide_index=True
)
