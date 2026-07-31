import joblib
import pandas as pd
import numpy as np

model = joblib.load('model/xgb_final_model.pkl')
feature_names = list(model.feature_names_in_)

raw_data = pd.read_csv('raw_data.csv', nrows=1)
row_dict = raw_data.iloc[0].to_dict()

df = pd.DataFrame(np.zeros((1, len(feature_names))), columns=feature_names)

for feature in feature_names:
    if feature in row_dict:
        val = row_dict[feature]
        if pd.notna(val):
            try:
                df[feature] = float(val)
            except:
                pass
    else:
        # Check if it's one-hot encoded
        for col, val in row_dict.items():
            if pd.notna(val) and isinstance(val, str):
                if feature == f"{col}_{val}":
                    df[feature] = 1.0
                    break

prob = model.predict_proba(df)[0][1]
print(f"Prediction using all features: {prob}")

# Prediction using only the 3 basic features
df_basic = pd.DataFrame(np.zeros((1, len(feature_names))), columns=feature_names)
if 'AMT_INCOME_TOTAL' in feature_names: df_basic['AMT_INCOME_TOTAL'] = row_dict['AMT_INCOME_TOTAL']
if 'AMT_CREDIT' in feature_names: df_basic['AMT_CREDIT'] = row_dict['AMT_CREDIT']
if 'DAYS_BIRTH' in feature_names: df_basic['DAYS_BIRTH'] = row_dict['DAYS_BIRTH']

prob_basic = model.predict_proba(df_basic)[0][1]
print(f"Prediction using basic features: {prob_basic}")
