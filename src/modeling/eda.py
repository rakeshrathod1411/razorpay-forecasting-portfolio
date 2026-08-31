import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import os
import seaborn as sns

# Config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "..", "data", "financial_data.db")
PLOTS_DIR = os.path.join(BASE_DIR, "..", "data", "plots")

# Ensure plot directory exists
os.makedirs(PLOTS_DIR, exist_ok=True)
# Set aesthetic style
sns.set_theme(style="whitegrid")

def run_eda():
    print(f"Connecting to DB at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Overall Revenue Trend (Platform Level)
    print("Generating platform revenue trend plot...")
    query_platform_rev = '''
        SELECT agg_date, SUM(gross_revenue) as total_revenue, SUM(total_transactions) as total_txns
        FROM daily_aggregates
        GROUP BY agg_date
        ORDER BY agg_date
    '''
    df_platform = pd.read_sql(query_platform_rev, conn, parse_dates=['agg_date'])
    
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(df_platform['agg_date'], df_platform['total_revenue'], color='b', alpha=0.7)
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Gross Revenue (₹)', color='b')
    ax1.tick_params(axis='y', labelcolor='b')
    ax1.set_title('Daily Gross Revenue and Transaction Volume Over Time')
    
    ax2 = ax1.twinx()
    ax2.plot(df_platform['agg_date'], df_platform['total_txns'], color='r', alpha=0.4)
    ax2.set_ylabel('Total Transactions', color='r')
    ax2.tick_params(axis='y', labelcolor='r')
    
    fig.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'platform_revenue_trend.png'))
    plt.close()
    
    # 2. Revenue by Business Category
    print("Generating category revenue plot...")
    query_category = '''
        SELECT m.business_category, SUM(d.net_revenue) as total_net_revenue
        FROM daily_aggregates d
        JOIN merchants m ON d.merchant_id = m.merchant_id
        GROUP BY m.business_category
        ORDER BY total_net_revenue DESC
    '''
    df_cat = pd.read_sql(query_category, conn)
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df_cat, y='business_category', x='total_net_revenue', palette='viridis')
    plt.title('Total Net Revenue by Business Category')
    plt.xlabel('Net Revenue (₹)')
    plt.ylabel('Category')
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'revenue_by_category.png'))
    plt.close()

    # 3. Payment Method Distribution
    print("Generating payment method distribution plot...")
    query_payment = '''
        SELECT payment_method, COUNT(*) as txn_count, SUM(transaction_amount) as total_amount
        FROM transactions
        GROUP BY payment_method
    '''
    df_pay = pd.read_sql(query_payment, conn)
    # Remove nulls if any
    df_pay = df_pay.dropna(subset=['payment_method'])
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    ax1.pie(df_pay['txn_count'], labels=df_pay['payment_method'], autopct='%1.1f%%', startangle=90, colors=sns.color_palette("pastel"))
    ax1.set_title('Transaction Count by Payment Method')
    
    ax2.pie(df_pay['total_amount'], labels=df_pay['payment_method'], autopct='%1.1f%%', startangle=90, colors=sns.color_palette("muted"))
    ax2.set_title('Total Revenue by Payment Method')
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'payment_methods.png'))
    plt.close()
    
    # 4. Success vs Failure vs Refund rate over time
    print("Generating transaction status rates plot...")
    df_platform['success_rate'] = (df_platform['total_txns'] - df_platform['total_revenue']*0) # Approximation, need better query
    query_rates = '''
        SELECT agg_date, 
               SUM(successful_transactions) * 100.0 / SUM(total_transactions) as success_rate,
               SUM(failed_transactions) * 100.0 / SUM(total_transactions) as failure_rate,
               SUM(refunded_transactions) * 100.0 / SUM(total_transactions) as refund_rate
        FROM daily_aggregates
        GROUP BY agg_date
        ORDER BY agg_date
    '''
    df_rates = pd.read_sql(query_rates, conn, parse_dates=['agg_date'])
    
    plt.figure(figsize=(12, 6))
    plt.plot(df_rates['agg_date'], df_rates['success_rate'], label='Success Rate (%)', color='green')
    plt.plot(df_rates['agg_date'], df_rates['failure_rate'], label='Failure Rate (%)', color='red')
    plt.plot(df_rates['agg_date'], df_rates['refund_rate'], label='Refund Rate (%)', color='orange')
    plt.title('Daily Transaction Status Rates')
    plt.xlabel('Date')
    plt.ylabel('Rate (%)')
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'transaction_rates.png'))
    plt.close()
    
    conn.close()
    print(f"EDA complete! Plots saved in {PLOTS_DIR}")

if __name__ == "__main__":
    run_eda()
