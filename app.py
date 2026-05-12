import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(layout="wide", page_title="Cash Flow & Inventory Simulator")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("Simulation Parameters")
    duration = st.number_input("Simulation Duration (Days)", value=100)
    
    st.subheader("Inventory Settings")
    avg_demand = st.number_input("Average Daily Demand", value=20)
    std_demand = st.number_input("Demand Variability (Std Dev)", value=5)
    lead_time = st.number_input("Lead Time (Days)", value=5)
    
    st.subheader("Cost & Credit Settings")
    unit_cost = st.number_input("Unit Purchase Price ($)", value=50)
    selling_price = st.number_input("Unit Selling Price ($)", value=80)
    order_cost = st.number_input("Ordering Cost (per order)", value=100)
    holding_cost_pct = st.number_input("Annual Holding Cost %", value=20) / 365
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)

# --- Simulation Logic ---
def run_simulation():
    # Initial states
    inventory = avg_demand * lead_time * 1.25  # Starting stock
    cash = 0
    pipeline_orders = [] # list of dicts: {'delivery_day': int, 'qty': int, 'payment_day': int}
    pending_receivables = [] # list of dicts: {'payment_day': int, 'amount': float}
    
    history = []
    rop = avg_demand * lead_time # Simple ROP
    order_qty = avg_demand * 10  # Economic Order Quantity simplified
    
    for day in range(duration):
        # 1. Demand realization
        daily_demand = max(0, int(np.random.normal(avg_demand, std_demand)))
        
        # 2. Fulfill Sales
        sales_units = min(inventory, daily_demand)
        stock_out = daily_demand - sales_units
        inventory -= sales_units
        
        # Record Receivable
        revenue = sales_units * selling_price
        if revenue > 0:
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': revenue})
            
        # 3. Check Deliveries
        arrived = [o for o in pipeline_orders if o['delivery_day'] <= day]
        for o in arrived:
            inventory += o['qty']
            pipeline_orders.remove(o)
            
        # 4. Ordering Logic
        if (inventory + sum(o['qty'] for o in pipeline_orders)) < rop:
            delivery_day = day + lead_time
            payment_day = delivery_day + supplier_credit
            pipeline_orders.append({
                'delivery_day': delivery_day, 
                'qty': order_qty, 
                'payment_day': payment_day,
                'cost': order_qty * unit_cost + order_cost
            })
            
        # 5. Cash Movements
        # Inflow
        inflow = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        # Outflow (Payments to suppliers)
        outflow = sum(o['cost'] for o in pipeline_orders if o.get('payment_day') == day)
        
        daily_holding_cost = inventory * (unit_cost * holding_cost_pct)
        cash += (inflow - outflow - daily_holding_cost)
        
        history.append({
            "Day": day,
            "Inventory": inventory,
            "Cash": cash,
            "Stockout_Days": 1 if stock_out > 0 else 0,
            "Holding_Cost": daily_holding_cost,
            "Order_Event": 1 if any(o['delivery_day'] == day + lead_time for o in pipeline_orders) else 0
        })
        
    return pd.DataFrame(history)

df_res = run_simulation()

# --- Dashboard ---
st.title("📦 AI Inventory & Cash Flow Auditor")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Avg Inventory", f"{df_res['Inventory'].mean():.2f} units")
m2.metric("Stock-out Days", f"{df_res['Stockout_Days'].sum()} days")
m3.metric("Total Holding Cost", f"${df_res['Holding_Cost'].sum():.2f}")
m4.metric("Total Orders Placed", f"{df_res['Order_Event'].sum()}")

# --- Visualizations ---
st.subheader("Inventory Movement & Cash Position")
fig = px.line(df_res, x="Day", y=["Inventory", "Cash"], 
              title="Inventory Levels vs Cumulative Cash Flow",
              labels={"value": "Quantity / $", "variable": "Metric"})
st.plotly_chart(fig, use_container_width=True)
