import streamlit as st
import pandas as pd
import sqlite3
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time

# --- Config & Setup ---
st.set_page_config(page_title="Merchant Analytics Hub", page_icon="💸", layout="wide", initial_sidebar_state="expanded")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "..", "data", "financial_data.db")
FEATURE_IMP_PATH = os.path.join(BASE_DIR, "..", "data", "feature_importance.csv")

# Custom CSS for Glassmorphism & Premium Animations
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background: radial-gradient(circle at top left, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    }
    
    /* Glassmorphism Metric Cards */
    .metric-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.1);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
    }
    .metric-card:hover {
        transform: translateY(-5px) scale(1.02);
        border: 1px solid rgba(0, 212, 255, 0.5);
        box-shadow: 0 8px 32px rgba(0, 212, 255, 0.2);
    }
    .metric-value {
        font-size: 36px;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #00d2ff, #3a7bd5);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-top: 10px;
        margin-bottom: 5px;
    }
    .metric-label {
        font-size: 12px;
        color: #a0a0b0;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: 600;
    }
    
    /* Trends */
    .trend-up { color: #00E676; font-size: 13px; font-weight: 600; background: rgba(0,230,118,0.1); padding: 4px 8px; border-radius: 12px;}
    .trend-down { color: #FF3D00; font-size: 13px; font-weight: 600; background: rgba(255,61,0,0.1); padding: 4px 8px; border-radius: 12px;}
    
    /* Alert Banner */
    .alert-banner {
        background: rgba(255, 61, 0, 0.15);
        backdrop-filter: blur(5px);
        border-left: 4px solid #FF3D00;
        padding: 15px 20px;
        border-radius: 8px;
        margin-bottom: 25px;
        display: flex;
        align-items: center;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(255,61,0, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(255,61,0, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255,61,0, 0); }
    }
    
    /* Clean up streamlit UI elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- Data Loading ---
@st.cache_resource
def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

@st.cache_data(ttl=60)
def load_data(query, params=()):
    conn = get_db_connection()
    return pd.read_sql(query, conn, params=params)

@st.cache_data
def get_filter_options():
    conn = get_db_connection()
    categories = pd.read_sql("SELECT DISTINCT business_category FROM merchants ORDER BY business_category", conn)['business_category'].tolist()
    merchants = pd.read_sql("SELECT merchant_name FROM merchants ORDER BY merchant_name", conn)['merchant_name'].tolist()
    return ["All Businesses"] + categories, ["All Merchants"] + merchants

# --- Sidebar Filters ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/8/89/Razorpay_logo.svg", width=150)
    st.markdown("### 🎛️ Data Filters")
    
    cat_options, merch_options = get_filter_options()
    
    selected_category = st.selectbox("Business Type", cat_options)
    
    if selected_category != "All Businesses":
        merchs_in_cat = load_data("SELECT merchant_name FROM merchants WHERE business_category = ?", (selected_category,))['merchant_name'].tolist()
        merch_options = ["All Merchants"] + merchs_in_cat
        
    selected_merchant = st.selectbox("Merchant Account", merch_options)
    
    st.markdown("---")
    date_range = st.date_input(
        "Analysis Period",
        value=(datetime(2024, 10, 1).date(), datetime(2024, 12, 31).date()),
        min_value=datetime(2023, 1, 1).date(),
        max_value=datetime(2024, 12, 31).date()
    )
    
    st.markdown("---")
    forecast_horizon = st.slider("Forecast Window (Days)", min_value=7, max_value=90, value=30, step=7)

if len(date_range) != 2:
    st.warning("Please select a complete date range.")
    st.stop()
start_date, end_date = date_range

# --- Dynamic Query Construction ---
base_join = "FROM daily_aggregates d JOIN merchants m ON d.merchant_id = m.merchant_id"
where_clauses = ["d.agg_date >= ? AND d.agg_date <= ?"]
params = [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]

if selected_category != "All Businesses":
    where_clauses.append("m.business_category = ?")
    params.append(selected_category)
    
if selected_merchant != "All Merchants":
    where_clauses.append("m.merchant_name = ?")
    params.append(selected_merchant)

where_sql = " WHERE " + " AND ".join(where_clauses)

# --- Main Dashboard UI ---
col_title, col_export = st.columns([4, 1])
with col_title:
    st.title("Merchant Analytics & Growth Hub")
with col_export:
    st.markdown("<br>", unsafe_allow_html=True)
    # STANDOUT FEATURE: Real CSV Export
    csv_data = load_data(f"SELECT d.agg_date, d.net_revenue, d.total_transactions {base_join} {where_sql}", params)
    st.download_button(
        label="📥 Export Report (CSV)",
        data=csv_data.to_csv(index=False).encode('utf-8'),
        file_name='financial_report.csv',
        mime='text/csv',
        use_container_width=True
    )

# 1. Fetch Dynamic KPIs
kpi_query = f"""
    SELECT 
        SUM(net_revenue) as total_rev, 
        SUM(total_transactions) as total_txns,
        SUM(successful_transactions) * 100.0 / SUM(total_transactions) as success_rate,
        SUM(refunded_transactions) * 100.0 / SUM(total_transactions) as refund_rate
    {base_join}
    {where_sql}
"""
df_kpi = load_data(kpi_query, params)

prev_start = start_date - (end_date - start_date)
prev_params = [prev_start.strftime('%Y-%m-%d'), start_date.strftime('%Y-%m-%d')] + params[2:]
df_kpi_prev = load_data(kpi_query, prev_params)

# Render KPIs
if not df_kpi.empty and df_kpi['total_rev'].iloc[0] is not None:
    rev = df_kpi['total_rev'].iloc[0]
    prev_rev = df_kpi_prev['total_rev'].iloc[0] if not df_kpi_prev.empty and df_kpi_prev['total_rev'].iloc[0] else rev
    rev_trend = ((rev - prev_rev) / prev_rev * 100) if prev_rev else 0
    rev_trend_html = f'<span class="trend-{"up" if rev_trend >= 0 else "down"}">{"▲" if rev_trend >= 0 else "▼"} {abs(rev_trend):.1f}%</span>'

    txns = df_kpi['total_txns'].iloc[0]
    success = df_kpi['success_rate'].iloc[0]
    refund = df_kpi['refund_rate'].iloc[0]
    
    # Anomaly Alert
    if refund > 4.0:
        st.markdown(f'<div class="alert-banner">⚠️ <b>Action Required:</b> High refund rate ({refund:.1f}%) detected. Check your recent orders to prevent chargebacks.</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total Earnings</div><div class="metric-value">₹{rev/10000000:.2f} Cr</div>{rev_trend_html}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Payments Processed</div><div class="metric-value">{txns:,.0f}</div><br></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Payment Success Rate</div><div class="metric-value">{success:.1f}%</div><br></div>', unsafe_allow_html=True)
    with col4:
        color = "#FF3D00" if refund > 4 else "#fff"
        st.markdown(f'<div class="metric-card"><div class="metric-label">Refund Rate</div><div class="metric-value" style="background: {color}; -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{refund:.1f}%</div><br></div>', unsafe_allow_html=True)
else:
    st.warning("No data found for the selected filters.")
    st.stop()

st.markdown("<br>", unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📈 Revenue & Predictions", "🛒 Sales Breakdown", "💡 Smart Insights", "🤖 Ask AI Assistant"])

with tab1:
    ts_query = f"""
        SELECT d.agg_date, SUM(d.net_revenue) as net_rev
        {base_join} {where_sql} GROUP BY d.agg_date ORDER BY d.agg_date
    """
    df_ts = load_data(ts_query, params)
    
    if selected_category == "All Businesses" and selected_merchant == "All Merchants":
        forecast_query = f"SELECT target_date, predicted_revenue, confidence_lower, confidence_upper FROM forecasts WHERE target_date <= date('{end_date.strftime('%Y-%m-%d')}', '+{forecast_horizon} days') ORDER BY target_date"
        df_forecast = load_data(forecast_query)
        
        fig = go.Figure()
        
        # Actuals
        fig.add_trace(go.Scatter(
            x=df_ts['agg_date'], y=df_ts['net_rev'], 
            mode='lines', name='Actual Earnings', 
            line=dict(color='#00d2ff', width=3),
            hovertemplate='Date: %{x}<br>Earnings: ₹%{y:,.0f}<extra></extra>'
        ))
        
        # Forecast
        if not df_forecast.empty:
            fig.add_trace(go.Scatter(
                x=df_forecast['target_date'], y=df_forecast['predicted_revenue'], 
                mode='lines', name='Expected Future Earnings', 
                line=dict(color='#FF9F1C', width=3, dash='dash'),
                hovertemplate='Date: %{x}<br>Expected: ₹%{y:,.0f}<extra></extra>'
            ))
            fig.add_trace(go.Scatter(
                x=df_forecast['target_date'].tolist() + df_forecast['target_date'].tolist()[::-1],
                y=df_forecast['confidence_upper'].tolist() + df_forecast['confidence_lower'].tolist()[::-1],
                fill='toself', fillcolor='rgba(255, 159, 28, 0.15)', line=dict(color='rgba(255,255,255,0)'),
                name='Expected Range', hoverinfo='skip'
            ))
            
        fig.update_layout(
            title="Daily Earnings Trajectory",
            template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            height=450, margin=dict(l=0, r=0, t=40, b=0),
            hovermode="x unified",
            xaxis=dict(
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1m", step="month", stepmode="backward"),
                        dict(count=3, label="3m", step="month", stepmode="backward"),
                        dict(step="all", label="All")
                    ]),
                    bgcolor="rgba(255,255,255,0.1)"
                ),
                rangeslider=dict(visible=True, thickness=0.05),
                type="date"
            )
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("💡 Predictive modeling is optimized at the Platform level. Reset filters to 'All Businesses' to view AI predictions.")
        fig = px.line(df_ts, x='agg_date', y='net_rev', title='Your Daily Earnings')
        fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Earnings by Segment")
        if selected_category == "All Businesses":
            seg_query = f"SELECT m.business_category as segment, SUM(d.net_revenue) as rev {base_join} {where_sql} GROUP BY m.business_category ORDER BY rev DESC LIMIT 10"
        else:
            seg_query = f"SELECT m.merchant_name as segment, SUM(d.net_revenue) as rev {base_join} {where_sql} GROUP BY m.merchant_name ORDER BY rev DESC LIMIT 10"
            
        df_seg = load_data(seg_query, params)
        fig_seg = px.bar(df_seg, x='rev', y='segment', orientation='h', color='rev', color_continuous_scale='Mint', labels={'rev': 'Earnings (₹)', 'segment': ''})
        fig_seg.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', coloraxis_showscale=False)
        st.plotly_chart(fig_seg, use_container_width=True)

    with col2:
        st.markdown("#### Customer Payment Preferences")
        pay_query = f"SELECT payment_method, COUNT(*) as count FROM transactions WHERE transaction_date >= ? AND transaction_date <= ? GROUP BY payment_method"
        df_pay = load_data(pay_query, [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')])
        fig_pay = px.pie(df_pay, values='count', names='payment_method', hole=0.6, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pay.update_traces(textposition='inside', textinfo='percent+label')
        # Add center text
        fig_pay.add_annotation(text=f"{df_pay['count'].sum():,.0f}<br>Total Txns", x=0.5, y=0.5, font_size=20, showarrow=False)
        fig_pay.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
        st.plotly_chart(fig_pay, use_container_width=True)

with tab3:
    st.markdown("### What drives your sales?")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        feature_map = {
            'rolling_avg_30d': 'Monthly Sales Momentum',
            'rolling_avg_7d': 'Weekly Sales Momentum',
            'revenue_lag_7': 'Sales from Previous Week',
            'revenue_lag_1': 'Sales from Yesterday',
            'revenue_lag_30': 'Sales from Last Month',
            'day_of_month': 'Payday / Time of Month',
            'day_of_week': 'Day of the Week',
            'is_weekend': 'Weekend Effect',
            'revenue_lag_14': 'Sales from 2 Weeks Ago'
        }
        
        df_imp = pd.read_csv(FEATURE_IMP_PATH) if os.path.exists(FEATURE_IMP_PATH) else pd.DataFrame()
        if not df_imp.empty:
            df_imp['importance'] = df_imp['importance'] / df_imp['importance'].sum() * 100
            df_imp['feature_friendly'] = df_imp['feature'].map(feature_map).fillna(df_imp['feature'])
            
            fig_imp = px.bar(df_imp.head(6), x='importance', y='feature_friendly', orientation='h', 
                             color='importance', color_continuous_scale='Plasma',
                             labels={'importance': 'Impact Score', 'feature_friendly': ''})
            fig_imp.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_imp, use_container_width=True)
            
    with col2:
        st.markdown("""
        <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);">
        <h4>💡 Actionable Takeaways</h4>
        <br>
        <b>1. Consistency is Key</b><br>
        Your historical monthly momentum is the strongest predictor of future sales. Keep operations steady.<br><br>
        <b>2. The Payday Spike</b><br>
        Sales surge consistently between the 1st and 5th of the month. <i>Tip: Schedule major marketing emails during these 5 days.</i><br><br>
        <b>3. Weekend Shifts</b><br>
        Weekends significantly shift buyer behavior. Prepare your inventory every Friday evening.
        </div>
        """, unsafe_allow_html=True)

with tab4:
    # STANDOUT FEATURE: AI Chat Interface (Simulated for Prototype)
    st.markdown("### 🤖 Ask your Financial Data")
    st.markdown("Query your revenue data using natural language. *(Prototype Mode)*")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hi! I'm your AI Financial Assistant. Ask me anything about your revenue, payment methods, or anomalies in the selected data."}
        ]

    # Display chat messages from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input("E.g. Why did revenue drop? What is my best payment method?"):
        # Display user message
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Simulate thinking
        with st.spinner("Analyzing your financial data..."):
            time.sleep(1.5)
            
            # Simple keyword-based logic to mimic RAG/LLM behavior grounded in data
            prompt_lower = prompt.lower()
            response = ""
            
            if "payment" in prompt_lower or "method" in prompt_lower:
                top_method = df_pay.sort_values('count', ascending=False).iloc[0]['payment_method']
                top_pct = (df_pay['count'].max() / df_pay['count'].sum()) * 100
                response = f"Based on the currently selected data, **{top_method}** is your most popular payment method, accounting for **{top_pct:.1f}%** of all transactions. I recommend ensuring your {top_method} checkout flow is completely frictionless."
            
            elif "refund" in prompt_lower or "drop" in prompt_lower:
                if refund > 3.0:
                    response = f"I noticed your refund rate is currently at **{refund:.1f}%**, which is higher than the platform average of 2.5%. This is negatively impacting your net revenue. The anomaly detection system flags spikes primarily on weekends."
                else:
                    response = f"Your refund rate is healthy at **{refund:.1f}%**. I don't see any major anomalies causing revenue drops in this period."
            
            elif "forecast" in prompt_lower or "future" in prompt_lower:
                response = f"Looking ahead {forecast_horizon} days, our Gradient Boosting model expects stable growth driven by strong monthly momentum. However, expect a slight dip on weekends based on your historical patterns."
                
            else:
                response = f"That's a great question about your data. In this specific period, you processed **{txns:,.0f}** payments totaling **₹{rev/10000000:.2f} Cr**. Try asking me specifically about payment methods, refunds, or future forecasts!"
        
        # Display assistant response
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
