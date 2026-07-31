import app
import pandas as pd
import random
from datetime import datetime, timedelta
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def generate_50_clients():
    print("Loading raw_data.csv...")
    df = pd.read_csv('raw_data.csv')
    
    # We want a mix of likely low risk and likely high risk.
    # TARGET = 0 usually has lower risk, TARGET = 1 has higher risk.
    df_low = df[df['TARGET'] == 0].sample(35, random_state=42)
    df_high = df[df['TARGET'] == 1].sample(15, random_state=42)
    
    df_sample = pd.concat([df_low, df_high]).sample(frac=1, random_state=42).reset_index(drop=True)
    
    arabic_names_male = ["أحمد", "محمد", "يوسف", "عمر", "علي", "عبدالله", "خالد", "حسن", "إبراهيم", "طارق", "سعيد", "محمود"]
    arabic_names_female = ["فاطمة", "مريم", "عائشة", "سارة", "زينب", "نورة", "ليلى", "هدى", "سميرة", "منى"]
    families = ["العلوي", "العمراني", "المنصوري", "الفاسي", "الإدريسي", "البناني", "التازي", "الشكري", "الوهابي", "المرابط"]
    
    jobs_map = {
        'Laborers': 'عامل',
        'Sales staff': 'موظف مبيعات',
        'Core staff': 'موظف أساسي',
        'Managers': 'مدير',
        'Drivers': 'سائق',
        'High skill tech staff': 'تقني متخصص',
        'Accountants': 'محاسب',
        'Medicine staff': 'طاقم طبي',
        'Security staff': 'طاقم أمني',
        'Cooking staff': 'طباخ'
    }
    
    new_clients = []
    
    for i, row in df_sample.iterrows():
        row_dict = row.fillna("").to_dict()
        
        # Determine Gender for Name
        gender_code = row_dict.get('CODE_GENDER', 'M')
        if gender_code == 'F':
            name = random.choice(arabic_names_female) + " " + random.choice(families)
        else:
            name = random.choice(arabic_names_male) + " " + random.choice(families)
            
        age = int(-row_dict.get('DAYS_BIRTH', -10950) / 365)
        income = row_dict.get('AMT_INCOME_TOTAL', 5000)
        loan_amount = row_dict.get('AMT_CREDIT', 20000)
        
        job_eng = row_dict.get('OCCUPATION_TYPE', '')
        job = jobs_map.get(job_eng, 'أعمال حرة' if job_eng == "" else 'موظف قطاع خاص')
        
        finance_type = 'تقليدي' if row_dict.get('NAME_CONTRACT_TYPE') == 'Cash loans' else 'تشاركي'
        
        # Random date in the last 30 days
        days_ago = random.randint(0, 30)
        date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%d/%m/%Y")
        
        client = {
            'id': f"CLT-2025-50{i:03d}",
            'name': name,
            'age': age,
            'income': income,
            'loan_amount': loan_amount,
            'job': job,
            'finance_type': finance_type,
            'date': date_str
        }
        
        # Compute risk using ALL historical data to be extremely accurate
        client['risk_prob'] = app.predict_client_risk(client, historical_data=row_dict)
        client['risk_level'] = app.get_risk_level(client['risk_prob'])
        
        new_clients.append(client)
        app.save_client(client)
        
    print(f"Successfully added {len(new_clients)} clients to the database.")

if __name__ == "__main__":
    generate_50_clients()
