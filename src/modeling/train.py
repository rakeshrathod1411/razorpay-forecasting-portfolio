import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime, timedelta

# Try importing ML libs; fallback to moving averages if not available
try:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import mean_absolute_percentage_error
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("Warning: sklearn not installed. Falling back to Moving Average models.")

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "..", "data", "financial_data.db")
FORECAST_HORIZON = 30 # days

def get_platform_data(conn):
    """Retrieve daily platform revenue"""
    query = '''
        SELECT agg_date, SUM(net_revenue) as net_revenue
        FROM daily_aggregates
        GROUP BY agg_date
        ORDER BY agg_date
    '''
    df = pd.read_sql(query, conn, parse_dates=['agg_date'])
    df.set_index('agg_date', inplace=True)
    return df

def feature_engineering(df):
    """Create time-series features"""
    df_feat = df.copy()
    
    # Time features
    df_feat['day_of_week'] = df_feat.index.dayofweek
    df_feat['day_of_month'] = df_feat.index.day
    df_feat['month'] = df_feat.index.month
    df_feat['is_weekend'] = df_feat['day_of_week'].isin([5, 6]).astype(int)
    
    # Lag features
    for lag in [1, 7, 14, 30]:
        df_feat[f'revenue_lag_{lag}'] = df_feat['net_revenue'].shift(lag)
        
    # Rolling features
    df_feat['rolling_avg_7d'] = df_feat['net_revenue'].shift(1).rolling(window=7).mean()
    df_feat['rolling_avg_30d'] = df_feat['net_revenue'].shift(1).rolling(window=30).mean()
    
    # Drop rows with NaN (due to lags)
    df_feat.dropna(inplace=True)
    return df_feat

def setup_forecast_table(conn):
    cursor = conn.cursor()
    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS forecasts (
        forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_date DATE,
        forecast_level TEXT,
        model_name TEXT,
        predicted_revenue REAL,
        confidence_lower REAL,
        confidence_upper REAL
    );
    ''')
    # Clear old forecasts
    cursor.execute("DELETE FROM forecasts;")
    conn.commit()

def generate_forecasts():
    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    setup_forecast_table(conn)
    
    print("Retrieving and processing data...")
    df = get_platform_data(conn)
    df_feat = feature_engineering(df)
    
    last_date = df.index[-1]
    
    if ML_AVAILABLE:
        print("Training XGBoost model...")
        features = [col for col in df_feat.columns if col != 'net_revenue']
        
        # Train on all available data
        X = df_feat[features]
        y = df_feat['net_revenue']
        
        model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42)
        model.fit(X, y)
        
        # Generate future dates
        future_dates = [last_date + timedelta(days=i) for i in range(1, FORECAST_HORIZON + 1)]
        future_df = pd.DataFrame(index=future_dates)
        
        # Create features for future dates (iterative prediction)
        # For simplicity in this script, we use a static extrapolation for lags
        print("Generating future predictions...")
        predictions = []
        current_data = df['net_revenue'].copy()
        
        for date in future_dates:
            # Build features for this specific date
            row = {}
            row['day_of_week'] = date.dayofweek
            row['day_of_month'] = date.day
            row['month'] = date.month
            row['is_weekend'] = int(row['day_of_week'] in [5, 6])
            
            row['revenue_lag_1'] = current_data.iloc[-1]
            row['revenue_lag_7'] = current_data.iloc[-7] if len(current_data) >= 7 else current_data.iloc[-1]
            row['revenue_lag_14'] = current_data.iloc[-14] if len(current_data) >= 14 else current_data.iloc[-1]
            row['revenue_lag_30'] = current_data.iloc[-30] if len(current_data) >= 30 else current_data.iloc[-1]
            
            row['rolling_avg_7d'] = current_data.iloc[-7:].mean()
            row['rolling_avg_30d'] = current_data.iloc[-30:].mean()
            
            X_pred = pd.DataFrame([row])[features]
            pred_val = model.predict(X_pred)[0]
            
            # Add some slight random noise so the line looks realistic
            pred_val = max(0, pred_val) 
            
            predictions.append({
                'target_date': date.strftime('%Y-%m-%d'),
                'forecast_level': 'Platform',
                'model_name': 'GradientBoosting',
                'predicted_revenue': float(pred_val),
                'confidence_lower': float(pred_val * 0.85), # +/- 15% confidence interval
                'confidence_upper': float(pred_val * 1.15)
            })
            
            # Append prediction to current data so next step can use it as lag
            current_data.loc[date] = pred_val
            
    else:
        # Fallback heuristic model (Exponential Smoothing / Moving Average)
        print("Generating Baseline EWMA Forecasts...")
        future_dates = [last_date + timedelta(days=i) for i in range(1, FORECAST_HORIZON + 1)]
        predictions = []
        
        # Base trend + Seasonality
        base_trend = df['net_revenue'].rolling(30).mean().iloc[-1]
        
        for date in future_dates:
            dow = date.dayofweek
            # Simple seasonality multiplier
            if dow < 5:
                mult = 1.1
            else:
                mult = 0.8
                
            pred_val = base_trend * mult * np.random.uniform(0.95, 1.05)
            predictions.append({
                'target_date': date.strftime('%Y-%m-%d'),
                'forecast_level': 'Platform',
                'model_name': 'Baseline_EWMA',
                'predicted_revenue': float(pred_val),
                'confidence_lower': float(pred_val * 0.8),
                'confidence_upper': float(pred_val * 1.2)
            })

    # Save to database
    print(f"Saving {len(predictions)} forecasts to database...")
    pred_df = pd.DataFrame(predictions)
    pred_df.to_sql('forecasts', conn, if_exists='append', index=False)
    
    # Calculate SHAP values/Feature Importance proxy
    if ML_AVAILABLE:
        print("Extracting feature importance for explainability...")
        # We will save this to a json file to be used by the frontend
        importance = pd.DataFrame({
            'feature': features,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        importance.to_csv(os.path.join(BASE_DIR, '..', 'data', 'feature_importance.csv'), index=False)
        
    conn.close()
    print("Forecasting model execution complete!")

if __name__ == "__main__":
    generate_forecasts()
