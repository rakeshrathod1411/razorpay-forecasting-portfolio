import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import uuid
import os

# Configuration
NUM_MERCHANTS = 50
START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2024, 12, 31)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Categorical Distributions
BUSINESS_CATEGORIES = [
    "E-commerce", "Food & Delivery", "Travel", "Education", 
    "Healthcare", "SaaS", "Retail", "Entertainment", 
    "Financial Services", "Logistics"
]
PAYMENT_METHODS = ["UPI", "Credit Card", "Debit Card", "Net Banking", "Wallet"]
PAYMENT_WEIGHTS = [0.45, 0.20, 0.15, 0.12, 0.08]

def generate_merchants():
    print("Generating merchants...")
    merchants = []
    for _ in range(NUM_MERCHANTS):
        category = random.choice(BUSINESS_CATEGORIES)
        
        # Base daily transaction volume depending on size
        size_rnd = random.random()
        if size_rnd < 0.1: size, base_vol, base_ticket = "Enterprise", random.randint(50, 150), random.randint(500, 5000)
        elif size_rnd < 0.4: size, base_vol, base_ticket = "Mid-Market", random.randint(15, 49), random.randint(200, 2000)
        else: size, base_vol, base_ticket = "SMB", random.randint(2, 14), random.randint(100, 1000)
        
        merchants.append({
            "merchant_id": str(uuid.uuid4()),
            "merchant_name": f"Merchant_{random.randint(1000, 9999)}",
            "business_category": category,
            "business_size": size,
            "onboarding_date": START_DATE - timedelta(days=random.randint(0, 365)),
            "base_daily_volume": base_vol,
            "base_ticket_size": base_ticket,
            "growth_rate": random.uniform(1.05, 1.25) # 5% to 25% annual growth
        })
    return pd.DataFrame(merchants)

def apply_seasonality_and_trends(base_vol, date, growth_rate, category):
    days_since_start = (date - START_DATE).days
    
    # Growth Trend (Annualized)
    growth_multiplier = 1 + ((growth_rate - 1) * (days_since_start / 365.0))
    
    # Weekly Seasonality
    dow = date.weekday()
    if category in ["SaaS", "Education", "Financial Services"]:
        # B2B / Weekday heavy
        weekly_mult = 1.2 if dow < 5 else 0.5
    else:
        # B2C / Weekend heavy
        weekly_mult = 0.9 if dow < 5 else 1.3
        
    # Monthly Seasonality (Salary Week)
    dom = date.day
    monthly_mult = 1.2 if (dom <= 5 or dom >= 25) else 0.9
    
    # Festivals / Holidays
    holiday_mult = 1.0
    month = date.month
    if month == 10 or month == 11: holiday_mult = 1.4 # Diwali/Dussehra
    elif month == 12: holiday_mult = 1.2 # Year end
    
    # Anomalies
    anomaly_mult = 1.0
    if date in [datetime(2023, 5, 12), datetime(2024, 2, 8)]: # Gateway outage
        anomaly_mult = 0.2
    elif date in [datetime(2023, 9, 21), datetime(2024, 7, 15)]: # Viral event
        anomaly_mult = 3.0
        
    final_vol = max(1, int(base_vol * growth_multiplier * weekly_mult * monthly_mult * holiday_mult * anomaly_mult * random.uniform(0.9, 1.1)))
    return final_vol

def get_transaction_status(method, date):
    # Base success rates
    if method == "UPI": success_prob = 0.95
    elif "Card" in method: success_prob = 0.92
    else: success_prob = 0.90
    
    # Anomaly: High failure rate event
    if date == datetime(2024, 8, 5) and method == "UPI":
        success_prob = 0.60
        
    rand_val = random.random()
    if rand_val < success_prob:
        # Check for refund
        refund_prob = 0.03
        if date in [datetime(2023, 11, 20), datetime(2024, 1, 5)]: # High refund days
            refund_prob = 0.15
            
        if random.random() < refund_prob: return "Refunded"
        return "Successful"
    return "Failed"

def get_fee_rate(method):
    if method == "UPI": return 0.0
    elif method == "Credit Card": return 0.02
    elif method == "Debit Card": return 0.009
    elif method == "Net Banking": return 0.015
    else: return 0.018 # Wallet

def generate_transactions(merchants_df):
    print("Generating transactions... This may take a moment.")
    transactions = []
    
    current_date = START_DATE
    total_days = (END_DATE - START_DATE).days + 1
    
    for i, row in merchants_df.iterrows():
        if i % 10 == 0: print(f"Processing merchant {i+1}/{NUM_MERCHANTS}...")
        
        current_date = START_DATE
        while current_date <= END_DATE:
            daily_vol = apply_seasonality_and_trends(row['base_daily_volume'], current_date, row['growth_rate'], row['business_category'])
            
            for _ in range(daily_vol):
                # Generate timestamp within the day
                hour = random.choices(range(24), weights=[1,1,1,1,1,1,3,4,6,8,8,7,6,7,6,5,6,8,9,9,8,6,3,2])[0]
                minute = random.randint(0, 59)
                txn_time = current_date + timedelta(hours=hour, minutes=minute)
                
                # Transaction specifics
                method = random.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS)[0]
                status = get_transaction_status(method, current_date)
                
                # Amount from log-normal distribution around base ticket size
                amount = max(10, round(np.random.lognormal(mean=np.log(row['base_ticket_size']), sigma=0.5), 2))
                
                # Calculations
                fee = round(amount * get_fee_rate(method), 2) if status == "Successful" else 0.0
                refund_amt = amount if status == "Refunded" else 0.0
                net_settlement = round(amount - fee - refund_amt, 2) if status in ["Successful", "Refunded"] else 0.0
                
                transactions.append({
                    "transaction_id": str(uuid.uuid4()),
                    "merchant_id": row['merchant_id'],
                    "transaction_date": txn_time,
                    "transaction_amount": amount,
                    "payment_method": method,
                    "payment_status": status,
                    "processing_fee": fee,
                    "refund_amount": refund_amt,
                    "settlement_amount": net_settlement
                })
                
            current_date += timedelta(days=1)
            
    df = pd.DataFrame(transactions)
    
    # Inject some random nulls (approx 1%) into non-critical fields for realism
    # Using numpy instead of standard choice for better performance on large sets
    null_idx = np.random.choice(df.index, size=int(len(df)*0.01), replace=False)
    df.loc[null_idx, 'payment_method'] = np.nan
    
    return df

if __name__ == "__main__":
    merchants_df = generate_merchants()
    # Save merchants without the generation parameters
    merchants_export = merchants_df.drop(columns=['base_daily_volume', 'base_ticket_size', 'growth_rate'])
    
    merchants_file = os.path.join(DATA_DIR, "synthetic_merchants.csv")
    merchants_export.to_csv(merchants_file, index=False)
    print(f"Saved {len(merchants_export)} merchants to {merchants_file}")
    
    transactions_df = generate_transactions(merchants_df)
    
    transactions_file = os.path.join(DATA_DIR, "synthetic_transactions.csv")
    transactions_df.to_csv(transactions_file, index=False)
    print(f"Saved {len(transactions_df)} transactions to {transactions_file}")
    print("Data generation complete!")
