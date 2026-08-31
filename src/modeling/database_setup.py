import pandas as pd
import sqlite3
import os
from datetime import datetime

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
DB_PATH = os.path.join(DATA_DIR, "financial_data.db")
MERCHANTS_CSV = os.path.join(DATA_DIR, "synthetic_merchants.csv")
TRANSACTIONS_CSV = os.path.join(DATA_DIR, "synthetic_transactions.csv")

def setup_database():
    print(f"Creating database at {DB_PATH}...")
    
    # Remove existing DB if it exists to start fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Create Tables
    cursor.executescript('''
    CREATE TABLE merchants (
        merchant_id TEXT PRIMARY KEY,
        merchant_name TEXT,
        business_category TEXT,
        business_size TEXT,
        onboarding_date DATE
    );

    CREATE TABLE transactions (
        transaction_id TEXT PRIMARY KEY,
        merchant_id TEXT,
        transaction_date DATETIME,
        transaction_amount REAL,
        payment_method TEXT,
        payment_status TEXT,
        processing_fee REAL,
        refund_amount REAL,
        settlement_amount REAL,
        FOREIGN KEY(merchant_id) REFERENCES merchants(merchant_id)
    );

    CREATE TABLE daily_aggregates (
        agg_date DATE,
        merchant_id TEXT,
        gross_revenue REAL,
        net_revenue REAL,
        total_transactions INTEGER,
        successful_transactions INTEGER,
        failed_transactions INTEGER,
        refunded_transactions INTEGER,
        avg_transaction_value REAL,
        processing_fees REAL,
        refund_total REAL,
        PRIMARY KEY (agg_date, merchant_id),
        FOREIGN KEY(merchant_id) REFERENCES merchants(merchant_id)
    );
    ''')
    conn.commit()
    
    # 2. Load Merchants
    print("Loading merchants...")
    merchants_df = pd.read_csv(MERCHANTS_CSV)
    merchants_df.to_sql('merchants', conn, if_exists='append', index=False)
    
    # 3. Load Transactions (Using chunks for memory efficiency)
    print("Loading transactions... (This takes a moment due to 1M+ rows)")
    chunk_size = 100000
    for chunk in pd.read_csv(TRANSACTIONS_CSV, chunksize=chunk_size):
        chunk.to_sql('transactions', conn, if_exists='append', index=False)
        
    print("Base data loaded successfully.")
    
    # 4. Calculate and load Daily Aggregates (Phase 5 - KPIs)
    print("Calculating daily KPI aggregates...")
    
    # We do the aggregation via SQL for efficiency and directly insert it
    agg_query = '''
    INSERT INTO daily_aggregates
    SELECT 
        date(transaction_date) as agg_date,
        merchant_id,
        SUM(CASE WHEN payment_status = 'Successful' THEN transaction_amount ELSE 0 END) as gross_revenue,
        SUM(settlement_amount) as net_revenue,
        COUNT(*) as total_transactions,
        SUM(CASE WHEN payment_status = 'Successful' THEN 1 ELSE 0 END) as successful_transactions,
        SUM(CASE WHEN payment_status = 'Failed' THEN 1 ELSE 0 END) as failed_transactions,
        SUM(CASE WHEN payment_status = 'Refunded' THEN 1 ELSE 0 END) as refunded_transactions,
        AVG(CASE WHEN payment_status = 'Successful' THEN transaction_amount ELSE NULL END) as avg_transaction_value,
        SUM(processing_fee) as processing_fees,
        SUM(refund_amount) as refund_total
    FROM transactions
    GROUP BY date(transaction_date), merchant_id;
    '''
    
    cursor.execute(agg_query)
    conn.commit()
    
    # Verify aggregations
    cursor.execute("SELECT COUNT(*) FROM daily_aggregates;")
    agg_count = cursor.fetchone()[0]
    print(f"Created {agg_count} daily aggregate records.")
    
    # Create indexes for faster queries in the API/Dashboard
    print("Creating database indexes...")
    cursor.executescript('''
    CREATE INDEX idx_txn_date ON transactions(transaction_date);
    CREATE INDEX idx_txn_merchant ON transactions(merchant_id);
    CREATE INDEX idx_agg_date ON daily_aggregates(agg_date);
    CREATE INDEX idx_agg_merchant ON daily_aggregates(merchant_id);
    ''')
    conn.commit()
    
    conn.close()
    print("Database setup complete!")

if __name__ == "__main__":
    setup_database()
