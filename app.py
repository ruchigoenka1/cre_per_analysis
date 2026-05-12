import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(layout="wide", page_title="Inventory & Cash Flow Simulator")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("1. Simulation Control")
    duration = st.number_input("Simulation Duration (Days)", value=180, step=10)
    
    st.header("2. Inventory Policy")
    rop = st.number_input("Reorder Point (Units)", value=150, help="Order is triggered when Stock + Pipeline falls below this.")
    order_qty = st.number_input("Order Quantity (Units)", value=300)
    
    st.header("3. Demand & Lead Time")
    avg_demand = st.number_input("Avg. Daily Demand", value=20)
    std_demand = st.number_input("Demand Variability (Std Dev)", value=5)
    lead_time = st.number_input("Lead Time (Days)", value=7)
    
    st.header("4. Financials & Credit")
    unit_cost = st.number_input("Unit Cost ($)", value=50)
    selling_price = st.number_input("Selling Price ($)", value=90)
    order_cost = st.number_input("Cost per Order ($)", value=150)
    holding_cost_annual = st.number_input("Annual Holding Cost per Unit ($)", value=10.0)
    daily_holding_per_unit = holding_cost_annual / 365
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)

# --- Simulation Logic ---
def run_simulation():
    # Setup initial state
    # Starting stock is 1.25 * the Production Trigger (ROP) for stability
    inventory = int(1.25 * rop)
    cash = 0
    pipeline_orders = [] 
    pending_receivables = [] 
    
    history = []
    
    for day in range(duration):
        # 1. Demand 
        daily_demand = max(0, int(np.random.normal(avg_demand, std_demand)))
        
        # 2. Fulfill Sales
        sales_units = min(inventory, daily_demand)
        stock_out = daily_demand - sales_units
        inventory -= sales_units
        
        # 3. Track Receivables (Cash Inflow)
        revenue = sales_units * selling_price
        if revenue > 0:
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': revenue})
            
        # 4. Handle Incoming Shipments
        arrived_qty = 0
        # Identify orders arriving today
        for o in list(pipeline_orders):
            if o['delivery_day'] == day:
                inventory += o['qty']
                arrived_qty = o['qty']
                # Order stays in list until payment_day to track outflow
            
        # 5. Ordering Logic (ROP)
        current_pipeline = sum(o['qty'] for o in pipeline_orders if o['delivery_day'] > day)
        if (inventory + current_pipeline) <= rop:
            delivery_day = day + lead_time
            payment_day = delivery_day + supplier_credit
            pipeline_orders.append({
                'delivery_day': delivery_day, 
                'qty': order_qty, 
                'payment_day': payment_day,
                'cost': (order_qty * unit_cost) + order_cost
            })
            
        # 6. Cash Flow Calculations
        inflow = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        outflow = sum(o['cost'] for o in pipeline_orders if o['payment_day'] == day)
        
        # Daily holding cost (Physical inventory only)
        total_holding = inventory * daily_holding_per_unit
        
        cash += (inflow - outflow - total_holding)
        
        history.append({
            "Day": day,
            "Physical_Stock": inventory,
            "Demand": daily_demand,
            "Sales": sales_units,
            "Cash_Balance": round(cash, 2),
            "Stockout": 1 if stock_out > 0 else 0,
            "Inflow": inflow,
            "Outflow": outflow
        })
        
    return pd.DataFrame(history)

df_res = run_simulation()

# --- Dashboard ---
st.title("📊 Cash Flow & Inventory Simulation")

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Avg Inventory", f"{int(df_res['Physical_Stock'].mean())} units")
with m2:
    st.metric("Stock-out Days", f"{df_res['Stockout'].sum()} days")
with m3:
    st.metric("Ending Cash", f"${df_res['Cash_Balance'].iloc[-1]:,.2f}")
with m4:
    st.metric("Total Payments", f"${df_res['Outflow'].sum():,.0f}")

# --- Graphs ---
st.subheader("Inventory & Cash Flow Trends")
c1, c2 = st.columns(2)

with c1:
    fig_inv = px.line(df_res, x="Day", y="Physical_Stock", title="Inventory Movement",
                     color_discrete_sequence=['#0047AB']) # Professional blue
    st.plotly_chart(fig_inv, use_container_width=True)

with c2:
    fig_cash = px.area(df_res, x="Day", y="Cash_Balance", title="Cumulative Cash Position",
                      color_discrete_sequence=['#228B22'])
    st.plotly_chart(fig_cash, use_container_width=True)

# --- Data Table ---
st.divider()
st.subheader("📋 Daily Simulation Logs")
st.dataframe(df_res, use_container_width=True, hide_index=True)
