import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(layout="wide", page_title="Supply Chain Cash Auditor")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("Simulation Settings")
    if st.button("🔄 Refresh Simulation"):
        st.rerun()
    
    st.subheader("Inventory Policy")
    rop = st.number_input("Reorder Point", value=150)
    order_qty = st.number_input("Order Quantity", value=300)
    
    st.subheader("Financials")
    unit_cost = st.number_input("Unit Cost ($)", value=50)
    selling_price = st.number_input("Selling Price ($)", value=90)
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)
    
    st.subheader("Variables")
    duration = st.number_input("Duration (Days)", value=180)
    avg_demand = st.number_input("Avg. Daily Demand", value=20)
    std_demand = st.number_input("Demand Variability", value=5)
    lead_time = st.number_input("Lead Time (Days)", value=7)

def run_simulation():
    inventory = int(1.25 * rop)
    cash_balance = 0
    ar_balance = 0 
    ap_balance = 0 
    
    pipeline_orders = [] 
    pending_receivables = [] 
    history = []
    
    for day in range(duration):
        # 1. Demand & Sales Fulfillment
        daily_demand = max(0, int(np.random.normal(avg_demand, std_demand)))
        sales_units = min(inventory, daily_demand)
        inventory -= sales_units
        
        # 2. Book Accounts Receivable (AR)
        sale_value = sales_units * selling_price
        if sale_value > 0:
            ar_balance += sale_value
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': sale_value})
            
        # 3. Deliveries & Book Accounts Payable (AP)
        for o in list(pipeline_orders):
            if o['delivery_day'] == day:
                inventory += o['qty']
                ap_balance += o['payable_amount']
            
        # 4. Procurement (ROP Trigger)
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
            
        # 5. Settlement Logic (Cash Movements)
        # Payment Received (Clearing AR)
        payment_received = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        ar_balance -= payment_received
        
        # Payment Made (Clearing AP)
        payment_made = sum(o['payable_amount'] for o in pipeline_orders if o['payment_day'] == day)
        ap_balance -= payment_made
        
        # Final Cash Update
        cash_balance += (payment_received - payment_made)
        
        history.append({
            "Day": day,
            "Demand": daily_demand,
            "Inventory": inventory,
            "Outstanding AR": round(ar_balance, 2),
            "Outstanding AP": round(ap_balance, 2),
            "Payment Received": round(payment_received, 2),
            "Payment Made": round(payment_made, 2),
            "Cash Balance": round(cash_balance, 2),
            "Stockout": 1 if (daily_demand > sales_units) else 0
        })
        
    return pd.DataFrame(history)

df_res = run_simulation()

# --- Main Dashboard ---
st.title("🚜 Supply Chain Financial Diagnostic")

# Summary Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Ending Cash", f"${df_res['Cash Balance'].iloc[-1]:,.0f}")
m2.metric("Stock-out Days", f"{df_res['Stockout'].sum()}")
m3.metric("Peak AR", f"${df_res['Outstanding AR'].max():,.0f}")
m4.metric("Peak AP", f"${df_res['Outstanding AP'].max():,.0f}")

st.divider()

# --- Graphs ---
st.subheader("Inventory Levels")
fig_inv = px.line(df_res, x="Day", y="Inventory", line_shape="hv", 
                  color_discrete_sequence=['#0047AB'], height=350)
st.plotly_chart(fig_inv, use_container_width=True)

st.subheader("Credit & Cash Position")
fig_cash = px.line(df_res, x="Day", y=["Outstanding AR", "Outstanding AP", "Cash Balance"],
                   color_discrete_map={"Outstanding AR": "#0047AB", "Outstanding AP": "#E31A1C", "Cash Balance": "#2E8B57"},
                   height=450)
st.plotly_chart(fig_cash, use_container_width=True)

# --- Data Table ---
st.subheader("📋 Daily Transaction Ledger")
# Rearranging columns for professional audit view
cols = ["Day", "Demand", "Inventory", "Outstanding AR", "Outstanding AP", "Payment Received", "Payment Made", "Cash Balance"]
st.dataframe(df_res[cols], use_container_width=True, hide_index=True)
