import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import math

st.set_page_config(layout="wide", page_title="Inventory & Working Capital Auditor")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("Simulation Control")
    # In Streamlit, any widget change triggers a rerun. 
    # This button now simply acts as a trigger to refresh the random seed.
    generate_btn = st.button("🔄 Run New Simulation")
    
    st.subheader("Inventory Policy")
    # Use the calculated EOQ as a suggested value
    use_eoq = st.checkbox("Use Calculated EOQ for Order Qty", value=False)
    
    rop = st.number_input("Reorder Point (Units)", value=150)
    manual_order_qty = st.number_input("Manual Order Quantity", value=300)
    
    st.subheader("Cost & Demand Inputs")
    avg_demand = st.number_input("Avg. Daily Demand", value=20)
    std_demand = st.number_input("Demand Variability", value=5)
    lead_time = st.number_input("Lead Time (Days)", value=7)
    unit_cost = st.number_input("Unit Cost ($)", value=50)
    selling_price = st.number_input("Selling Price ($)", value=90)
    order_cost_fixed = st.number_input("Ordering Cost (per order) ($)", value=150)
    holding_cost_annual = st.number_input("Annual Holding Cost per Unit ($)", value=10.0)
    
    st.subheader("Credit Terms")
    supplier_credit = st.number_input("Supplier Credit (Days)", value=30)
    customer_credit = st.number_input("Customer Credit (Days)", value=15)
    duration = st.number_input("Duration (Days)", value=180)

# --- EOQ Calculation ---
annual_demand = avg_demand * 365
# EOQ Formula: sqrt((2 * Annual Demand * Ordering Cost) / Holding Cost)
calculated_eoq = math.sqrt((2 * annual_demand * order_cost_fixed) / holding_cost_annual)
order_qty = int(calculated_eoq) if use_eoq else manual_order_qty

def run_simulation():
    # Initial state
    inventory = int(1.25 * rop)
    cash_balance = 0
    ar_balance = 0 
    ap_balance = 0 
    
    pipeline_orders = [] 
    pending_receivables = [] 
    history = []
    
    daily_holding_rate = holding_cost_annual / 365
    total_ordering_paid = 0
    total_holding_paid = 0
    
    for day in range(duration):
        # 1. Demand & Sales
        daily_demand = max(0, int(np.random.normal(avg_demand, std_demand)))
        sales_units = min(inventory, daily_demand)
        inventory -= sales_units
        
        # 2. Book AR
        sale_value = sales_units * selling_price
        if sale_value > 0:
            ar_balance += sale_value
            pending_receivables.append({'payment_day': day + customer_credit, 'amount': sale_value})
            
        # 3. Deliveries & Book AP
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
                'qty': order_qty, 
                'payment_day': payment_day,
                'payable_amount': order_qty * unit_cost
            })
            total_ordering_paid += order_cost_fixed
            
        # 5. Settlement (Cash Movements)
        payment_received = sum(r['amount'] for r in pending_receivables if r['payment_day'] == day)
        ar_balance -= payment_received
        
        payment_made = sum(o['payable_amount'] for o in pipeline_orders if o['payment_day'] == day)
        ap_balance -= payment_made
        
        # 6. Expenses
        current_day_holding = inventory * daily_holding_rate
        total_holding_paid += current_day_holding
        
        cash_balance += (payment_received - payment_made)
        
        # Working Capital Calculation: AR + Inventory Value - AP
        working_capital = ar_balance + (inventory * unit_cost) - ap_balance
        
        history.append({
            "Day": day,
            "Demand": daily_demand,
            "Inventory": inventory,
            "Outstanding_AR": ar_balance,
            "Outstanding_AP": ap_balance,
            "Working_Capital": working_capital,
            "Payment_Received": payment_received,
            "Payment_Made": payment_made,
            "Cash_Balance": cash_balance,
            "Daily_Holding_Cost": current_day_holding
        })
        
    return pd.DataFrame(history), total_holding_paid, total_ordering_paid

df_res, total_hold, total_order = run_simulation()

# --- Dashboard ---
st.title("🚜 Supply Chain Working Capital Diagnostic")

# KPI Metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Calculated EOQ", f"{int(calculated_eoq)} units")
c2.metric("Avg Working Capital", f"${df_res['Working_Capital'].mean():,.0f}")
c3.metric("Total Holding Cost", f"${total_hold:,.0f}")
c4.metric("Total Ordering Cost", f"${total_order:,.0f}")

st.divider()

# --- Full Width Visualizations ---
st.subheader("Working Capital Requirement (AR + Inventory - AP)")

fig_wc = px.area(df_res, x="Day", y="Working_Capital", 
                 color_discrete_sequence=['#FF8C00'], height=400)
st.plotly_chart(fig_wc, use_container_width=True)

st.subheader("Inventory Levels (Step Chart)")
fig_inv = px.line(df_res, x="Day", y="Inventory", line_shape="hv", 
                  color_discrete_sequence=['#0047AB'], height=400)
fig_inv.add_hline(y=rop, line_dash="dot", line_color="red", annotation_text="Reorder Point")
st.plotly_chart(fig_inv, use_container_width=True)

st.subheader("Cumulative Cash Position")
fig_cash = px.area(df_res, x="Day", y="Cash_Balance", 
                   color_discrete_sequence=['#2E8B57'], height=400)
st.plotly_chart(fig_cash, use_container_width=True)

# --- Ledger ---
with st.expander("Detailed Daily Transaction Ledger"):
    st.dataframe(df_res, use_container_width=True, hide_index=True)
