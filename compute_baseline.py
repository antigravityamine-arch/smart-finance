import pandas as pd
import json

print("Loading raw_data.csv...")
df = pd.read_csv('raw_data.csv', low_memory=False)

baseline = {}

# Process categorical/string columns
for col in df.select_dtypes(include=['object', 'string']).columns:
    mode_val = df[col].mode()
    if len(mode_val) > 0:
        val = mode_val[0]
        baseline[col] = str(val) if pd.notna(val) else ""
    else:
        baseline[col] = ""

# Process numerical columns
for col in df.select_dtypes(include=['number']).columns:
    median_val = df[col].median()
    if pd.notna(median_val):
        baseline[col] = float(median_val)
    else:
        baseline[col] = 0.0

with open('baseline_profile.json', 'w', encoding='utf-8') as f:
    json.dump(baseline, f, ensure_ascii=False, indent=4)

print("Saved baseline profile to baseline_profile.json")
