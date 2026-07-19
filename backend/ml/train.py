import os
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, accuracy_score, roc_auc_score
from sklearn.linear_model import LogisticRegression
import xgboost as xgb

def train_models():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cvi_data_path = os.path.join(script_dir, 'data', 'cvi_synthetic_data.csv')
    mhs_data_path = os.path.join(script_dir, 'data', 'mhs_synthetic_data.csv')
    
    if not os.path.exists(cvi_data_path) or not os.path.exists(mhs_data_path):
        print("Data files not found. Generating synthetic data first...")
        from generate_synthetic_data import generate_dataset
        os.makedirs(os.path.join(script_dir, 'data'), exist_ok=True)
        cvi, mhs = generate_dataset()
        cvi.to_csv(cvi_data_path, index=False)
        mhs.to_csv(mhs_data_path, index=False)
    else:
        cvi = pd.read_csv(cvi_data_path)
        mhs = pd.read_csv(mhs_data_path)
        
    print("--- Training CVI Model (XGBoost Regressor) ---")
    X_cvi = cvi.drop(columns=['cvi_target'])
    y_cvi = cvi['cvi_target']
    
    X_train_cvi, X_test_cvi, y_train_cvi, y_test_cvi = train_test_split(
        X_cvi, y_cvi, test_size=0.2, random_state=42
    )
    
    cvi_model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        random_state=42
    )
    cvi_model.fit(X_train_cvi, y_train_cvi)
    
    # Evaluate
    preds_cvi = cvi_model.predict(X_test_cvi)
    mse = mean_squared_error(y_test_cvi, preds_cvi)
    r2 = r2_score(y_test_cvi, preds_cvi)
    print(f"CVI Model Test MSE: {mse:.4f}")
    print(f"CVI Model Test R2: {r2:.4f}")
    
    # Fit full and save
    cvi_model.fit(X_cvi, y_cvi)
    model_dir = os.path.join(os.path.dirname(script_dir), 'models')
    os.makedirs(model_dir, exist_ok=True)
    cvi_path = os.path.join(model_dir, 'cvi_model.joblib')
    joblib.dump(cvi_model, cvi_path)
    print(f"Saved CVI model to {cvi_path}")
    
    print("\n--- Training MHS Model (Logistic Regression) ---")
    X_mhs = mhs.drop(columns=['mhs_target'])
    y_mhs = mhs['mhs_target']
    
    X_train_mhs, X_test_mhs, y_train_mhs, y_test_mhs = train_test_split(
        X_mhs, y_mhs, test_size=0.2, random_state=42
    )
    
    mhs_model = LogisticRegression(random_state=42)
    mhs_model.fit(X_train_mhs, y_train_mhs)
    
    # Evaluate
    preds_mhs = mhs_model.predict(X_test_mhs)
    probs_mhs = mhs_model.predict_proba(X_test_mhs)[:, 1]
    acc = accuracy_score(y_test_mhs, preds_mhs)
    auc = roc_auc_score(y_test_mhs, probs_mhs)
    print(f"MHS Model Test Accuracy: {acc:.4f}")
    print(f"MHS Model Test ROC-AUC: {auc:.4f}")
    
    # Fit full and save
    mhs_model.fit(X_mhs, y_mhs)
    mhs_path = os.path.join(model_dir, 'mhs_model.joblib')
    joblib.dump(mhs_model, mhs_path)
    print(f"Saved MHS model to {mhs_path}")

if __name__ == '__main__':
    train_models()
