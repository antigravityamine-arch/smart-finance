from flask import Flask, render_template, request, jsonify, url_for, session, redirect, flash, Response
from functools import wraps
import pandas as pd
import numpy as np
import joblib
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = 'smart_finance_super_secret_key'

import sqlite3
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

DB_FILE = os.path.join(os.path.dirname(__file__), 'smart_finance.db')

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# تهيئة قاعدة البيانات الافتراضية
db = None
USE_FIREBASE = False

# التحقق بدقة 100% هل نحن على سيرفر PythonAnywhere أم محلياً
is_on_pythonanywhere = (
    'PYTHONANYWHERE_SITE' in os.environ or 
    'PYTHONANYWHERE_DOMAIN' in os.environ or 
    '/home/' in os.path.abspath(__file__)
)

def _test_firebase_connection():
    """فحص اتصال Firebase في thread منفصل لمنع أي تعليق"""
    cred_path = os.path.join(os.path.dirname(__file__), 'firebase_credentials.json')
    if not os.path.exists(cred_path):
        return None, "firebase_credentials.json not found"
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    client = firestore.client()
    # فحص حقيقي - محاولة قراءة مستند واحد
    client.collection('_connection_test').document('test').get()
    return client, "OK"

if not is_on_pythonanywhere:
    print("Local environment detected. Testing Firebase connection (max 3 seconds)...")
    try:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_test_firebase_connection)
        result_db, msg = future.result(timeout=3)
        if result_db:
            db = result_db
            USE_FIREBASE = True
            print("[OK] Firebase connected and verified successfully (Local Environment)")
        else:
            print(f"[WARN] {msg}, falling back to SQLite")
        # لا نستخدم with لكي لا ينتظر إغلاق الـ Thread الميت

    except (FutureTimeoutError, TimeoutError):
        db = None
        USE_FIREBASE = False
        print("[WARN] Firebase connection timed out (3s). Using SQLite locally.")
    except Exception as e:
        db = None
        USE_FIREBASE = False
        print(f"[WARN] Firebase error: {e}. Using SQLite locally.")
else:
    print("[INFO] PythonAnywhere detected. Using SQLite database.")

print(f"[INFO] Database mode: {'Firebase' if USE_FIREBASE else 'SQLite'}")

def get_all_clients():
    if USE_FIREBASE and db:
        try:
            docs = db.collection('clients').order_by('id', direction=firestore.Query.DESCENDING).stream(timeout=5.0)
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"Firestore get_all_clients error (timing out/offline): {e}")
            
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM clients ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return [json.loads(row['data']) for row in rows]
    except Exception as e:
        print(f"SQLite get_all_clients error: {e}")
        return []

def get_client(client_id):
    if USE_FIREBASE and db:
        try:
            doc = db.collection('clients').document(client_id).get(timeout=5.0)
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            print(f"Firestore get_client error (timing out/offline): {e}")
            
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM clients WHERE id = ?", (client_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row['data'])
    except Exception as e:
        print(f"SQLite get_client error: {e}")
    return None

def save_client(client_data):
    if USE_FIREBASE and db:
        try:
            db.collection('clients').document(client_data['id']).set(client_data, timeout=5.0)
            return
        except Exception as e:
            print(f"Firestore save_client error (timing out/offline): {e}")
            
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO clients (id, data) VALUES (?, ?)", (client_data['id'], json.dumps(client_data)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"SQLite save_client error: {e}")

def delete_client(client_id):
    if USE_FIREBASE and db:
        try:
            db.collection('clients').document(client_id).delete(timeout=5.0)
            return True
        except Exception as e:
            print(f"Firestore delete_client error (timing out/offline): {e}")
            
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"SQLite delete_client error: {e}")
        return False

def update_client(client_id, updated_data):
    if USE_FIREBASE and db:
        try:
            db.collection('clients').document(client_id).update(updated_data, timeout=5.0)
            return True
        except Exception as e:
            print(f"Firestore update_client error (timing out/offline): {e}")
            
    try:
        client = get_client(client_id)
        if client:
            client.update(updated_data)
            save_client(client)
            return True
    except Exception as e:
        print(f"SQLite update_client error: {e}")
    return False

def get_user(username):
    if USE_FIREBASE and db:
        try:
            doc = db.collection('users').document(username).get(timeout=5.0)
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            print(f"Firestore get_user error (timing out/offline): {e}")
            
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT password, full_name, created_at FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                'username': username,
                'password': row['password'],
                'full_name': row['full_name'],
                'created_at': row['created_at']
            }
    except Exception as e:
        print(f"SQLite get_user error: {e}")
    return None

def save_user(username, password, full_name):
    if USE_FIREBASE and db:
        try:
            db.collection('users').document(username).set({
                'username': username,
                'password': password,
                'full_name': full_name,
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, timeout=5.0)
            return True
        except Exception as e:
            print(f"Firestore save_user error (timing out/offline): {e}")
            
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (username, password, full_name, created_at) VALUES (?, ?, ?, ?)", 
                       (username, password, full_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"SQLite save_user error: {e}")
        return False

# تحميل النموذج
model = None
feature_names = []
model_path = os.path.join(os.path.dirname(__file__), 'model', 'xgb_final_model.pkl')
if os.path.exists(model_path):
    model = joblib.load(model_path)
    if hasattr(model, 'feature_names_in_'):
        feature_names = list(model.feature_names_in_)
    elif hasattr(model.get_booster(), 'feature_names'):
        feature_names = model.get_booster().feature_names

baseline_profile = {}
try:
    import json
    profile_path = os.path.join(os.path.dirname(__file__), 'baseline_profile.json')
    if os.path.exists(profile_path):
        with open(profile_path, 'r', encoding='utf-8') as f:
            baseline_profile = json.load(f)
except Exception as e:
    print(f"Error loading baseline profile: {e}")

# تحميل raw_data.zip المضغوط لتقليل حجم المشروع
raw_data_path = os.path.join(os.path.dirname(__file__), 'data', 'raw_data.zip')

# تحميل البيانات لـ Analytics
RAW_DATA = None
RAW_DATA_STATS = {}
if os.path.exists(raw_data_path):
    try:
        print("Loading raw_data.zip...")
        RAW_DATA = pd.read_csv(raw_data_path, compression='zip', encoding='utf-8', low_memory=False, on_bad_lines='skip')
        print(f"Loaded {len(RAW_DATA)} rows, {len(RAW_DATA.columns)} columns")
        
        # حساب الإحصائيات مسبقاً لتسريع الأداء
        total_rows = len(RAW_DATA)
        target_col = 'TARGET' if 'TARGET' in RAW_DATA.columns else None
        
        if target_col:
            RAW_DATA[target_col] = pd.to_numeric(RAW_DATA[target_col], errors='coerce').fillna(0)
            defaulted = int(RAW_DATA[target_col].sum())
            non_defaulted = total_rows - defaulted
            default_rate = round((defaulted / total_rows) * 100, 2) if total_rows > 0 else 0
        else:
            defaulted = 0
            non_defaulted = total_rows
            default_rate = 0
        
        # إحصائيات الدخل
        income_col = 'AMT_INCOME_TOTAL' if 'AMT_INCOME_TOTAL' in RAW_DATA.columns else None
        credit_col = 'AMT_CREDIT' if 'AMT_CREDIT' in RAW_DATA.columns else None
        gender_col = 'CODE_GENDER' if 'CODE_GENDER' in RAW_DATA.columns else None
        contract_col = 'NAME_CONTRACT_TYPE' if 'NAME_CONTRACT_TYPE' in RAW_DATA.columns else None
        education_col = 'NAME_EDUCATION_TYPE' if 'NAME_EDUCATION_TYPE' in RAW_DATA.columns else None
        family_col = 'NAME_FAMILY_STATUS' if 'NAME_FAMILY_STATUS' in RAW_DATA.columns else None
        housing_col = 'NAME_HOUSING_TYPE' if 'NAME_HOUSING_TYPE' in RAW_DATA.columns else None
        income_type_col = 'NAME_INCOME_TYPE' if 'NAME_INCOME_TYPE' in RAW_DATA.columns else None
        
        # توزيع الجنس
        gender_dist = {}
        if gender_col:
            gc = RAW_DATA[gender_col].value_counts()
            gender_dist = {str(k): int(v) for k, v in gc.items() if str(k) in ['M', 'F']}
        
        # توزيع نوع العقد
        contract_dist = {}
        if contract_col:
            cc = RAW_DATA[contract_col].value_counts()
            contract_dist = {str(k): int(v) for k, v in cc.items()}
        
        # توزيع التعليم
        education_dist = {}
        if education_col:
            ec = RAW_DATA[education_col].value_counts()
            education_dist = {str(k): int(v) for k, v in ec.items()}
        
        # توزيع الحالة العائلية
        family_dist = {}
        if family_col:
            fc = RAW_DATA[family_col].value_counts()
            family_dist = {str(k): int(v) for k, v in fc.items()}

        # توزيع نوع السكن
        housing_dist = {}
        if housing_col:
            hc = RAW_DATA[housing_col].value_counts()
            housing_dist = {str(k): int(v) for k, v in hc.items()}

        # توزيع نوع الدخل
        income_type_dist = {}
        if income_type_col:
            ic = RAW_DATA[income_type_col].value_counts()
            income_type_dist = {str(k): int(v) for k, v in ic.items()}
        
        # إحصائيات رقمية
        income_stats = {}
        if income_col:
            RAW_DATA[income_col] = pd.to_numeric(RAW_DATA[income_col], errors='coerce')
            income_stats = {
                'mean': round(float(RAW_DATA[income_col].mean(skipna=True)), 2),
                'median': round(float(RAW_DATA[income_col].median(skipna=True)), 2),
                'min': round(float(RAW_DATA[income_col].min(skipna=True)), 2),
                'max': round(float(RAW_DATA[income_col].max(skipna=True)), 2),
            }
        
        credit_stats = {}
        if credit_col:
            RAW_DATA[credit_col] = pd.to_numeric(RAW_DATA[credit_col], errors='coerce')
            credit_stats = {
                'mean': round(float(RAW_DATA[credit_col].mean(skipna=True)), 2),
                'median': round(float(RAW_DATA[credit_col].median(skipna=True)), 2),
                'min': round(float(RAW_DATA[credit_col].min(skipna=True)), 2),
                'max': round(float(RAW_DATA[credit_col].max(skipna=True)), 2),
            }
        
        # معدل التعثر حسب الجنس
        default_by_gender = {}
        if target_col and gender_col:
            for g in RAW_DATA[gender_col].dropna().unique():
                if str(g) in ['M', 'F']:
                    subset = RAW_DATA[RAW_DATA[gender_col] == g]
                    rate = round((subset[target_col].sum() / len(subset)) * 100, 2) if len(subset) > 0 else 0
                    default_by_gender[str(g)] = rate
        
        # معدل التعثر حسب نوع العقد
        default_by_contract = {}
        if target_col and contract_col:
            for c in RAW_DATA[contract_col].dropna().unique():
                subset = RAW_DATA[RAW_DATA[contract_col] == c]
                rate = round((subset[target_col].sum() / len(subset)) * 100, 2) if len(subset) > 0 else 0
                default_by_contract[str(c)] = rate

        # معدل التعثر حسب التعليم
        default_by_education = {}
        if target_col and education_col:
            for e in RAW_DATA[education_col].dropna().unique():
                subset = RAW_DATA[RAW_DATA[education_col] == e]
                rate = round((subset[target_col].sum() / len(subset)) * 100, 2) if len(subset) > 0 else 0
                default_by_education[str(e)] = rate

        # توزيع العمر (Histogram bins)
        age_distribution = []
        if 'DAYS_BIRTH' in RAW_DATA.columns:
            ages = (-RAW_DATA['DAYS_BIRTH'] / 365).dropna()
            bins = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
            labels = ['20-25', '25-30', '30-35', '35-40', '40-45', '45-50', '50-55', '55-60', '60-65', '65-70']
            age_bins = pd.cut(ages, bins=bins, labels=labels, right=False)
            age_counts = age_bins.value_counts().sort_index()
            age_distribution = [{'range': str(k), 'count': int(v)} for k, v in age_counts.items()]

        RAW_DATA_STATS = {
            'total_rows': total_rows,
            'total_columns': len(RAW_DATA.columns),
            'columns': list(RAW_DATA.columns),
            'defaulted': defaulted,
            'non_defaulted': non_defaulted,
            'default_rate': default_rate,
            'gender_dist': gender_dist,
            'contract_dist': contract_dist,
            'education_dist': education_dist,
            'family_dist': family_dist,
            'housing_dist': housing_dist,
            'income_type_dist': income_type_dist,
            'income_stats': income_stats,
            'credit_stats': credit_stats,
            'default_by_gender': default_by_gender,
            'default_by_contract': default_by_contract,
            'default_by_education': default_by_education,
            'age_distribution': age_distribution,
        }
        print("Raw data stats computed successfully.")
    except Exception as e:
        print(f"Error loading raw_data.csv: {e}")
        RAW_DATA = None

# قواعد القرار
def get_risk_level(prob):
    if prob < 0.15:
        return "منخفض"
    elif prob < 0.40:
        return "متوسط"
    else:
        return "مرتفع"

def conventional_decision(prob):
    if prob < 0.15:
        return {"decision": "قبول", "recommendation": "يمكن قبول التمويل دون شروط إضافية"}
    elif prob < 0.40:
        return {"decision": "قبول مع شروط", "recommendation": "تقليل مبلغ التمويل أو طلب ضمانات إضافية"}
    else:
        return {"decision": "رفض", "recommendation": "مخاطر التعثر مرتفعة جداً"}

def participative_decision(prob):
    if prob < 0.15:
        return {"contract": "مشاركة أو إجارة", "decision": "مقبول مبدئياً", "recommendation": "يمكن اعتماد صيغة مرنة حسب طبيعة الأصل"}
    elif prob < 0.40:
        return {"contract": "مرابحة", "decision": "مقبول مع ضمانات", "recommendation": "اعتماد مرابحة مع دفعة أولى عالية وضمانات كافية"}
    else:
        return {"contract": "غير مقترح", "decision": "مرفوض", "recommendation": "العملية محفوفة بالمخاطر، يرجى رفض التمويل"}

# إعدادات النظام
GLOBAL_SETTINGS = {
    'language': 'العربية',
    'currency': 'الدرهم المغربي (MAD)',
    'timezone': 'الدار البيضاء (GMT+1)',
    'display_mode': 'رسمي',
    'results_per_page': 5,
    'session_timeout': 30,
    'sharia_enabled': True,
    'sharia_source': 'AAOIFI',
    'sharia_update': '01/05/2025'
}

def predict_client_risk(client, historical_data=None):
    if model is not None and len(feature_names) > 0:
        df = pd.DataFrame(np.zeros((1, len(feature_names))), columns=feature_names)
        
        # 1. Use baseline profile for new clients, or historical_data for historical
        data_source = historical_data if historical_data is not None else baseline_profile
        
        if data_source:
            # Map 122 variables to the 210 one-hot encoded features
            for feature in feature_names:
                if feature in data_source:
                    val = data_source[feature]
                    if pd.notna(val) and val != "":
                        try:
                            df[feature] = float(val)
                        except:
                            pass
                else:
                    # Check for one-hot encoded features
                    for col, val in data_source.items():
                        if pd.notna(val) and isinstance(val, str) and val != "":
                            if feature == f"{col}_{val}":
                                df[feature] = 1.0
                                break
                                
        # 2. Override with the explicit user inputs from the UI
        if 'AMT_INCOME_TOTAL' in feature_names: df['AMT_INCOME_TOTAL'] = client.get('income', df['AMT_INCOME_TOTAL'].iloc[0])
        if 'AMT_CREDIT' in feature_names: df['AMT_CREDIT'] = client.get('loan_amount', df['AMT_CREDIT'].iloc[0])
        if 'DAYS_BIRTH' in feature_names: df['DAYS_BIRTH'] = -int(client.get('age', 30)) * 365
        
        prob = model.predict_proba(df.values)[0][1]
    else:
        np.random.seed(int(str(client['id']).split('-')[-1]))
        prob = np.random.uniform(0.05, 0.55)
    return float(prob)

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                data TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT,
                full_name TEXT,
                created_at TEXT
            )
        ''')
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM clients")
        if cursor.fetchone()[0] == 0:
            print("Seeding SQLite with mock data...")
            MOCK_DATA = [
                {"id": "CLT-2025-00125", "age": 34, "income": 12000, "loan_amount": 80000, "job": "موظف", "finance_type": "تشاركي", "date": "12/04/2025"},
                {"id": "CLT-2025-00124", "age": 28, "income": 8000, "loan_amount": 50000, "job": "موظف", "finance_type": "تقليدي", "date": "10/04/2025"},
                {"id": "CLT-2025-00123", "age": 45, "income": 15000, "loan_amount": 100000, "job": "تاجر", "finance_type": "تشاركي", "date": "09/04/2025"},
                {"id": "CLT-2025-00122", "age": 37, "income": 10000, "loan_amount": 70000, "job": "موظف", "finance_type": "تقليدي", "date": "08/04/2025"},
                {"id": "CLT-2025-00121", "age": 26, "income": 5500, "loan_amount": 30000, "job": "موظف", "finance_type": "تشاركي", "date": "07/04/2025"},
                {"id": "CLT-2025-00120", "age": 50, "income": 20000, "loan_amount": 150000, "job": "مدير", "finance_type": "تقليدي", "date": "06/04/2025"},
                {"id": "CLT-2025-00119", "age": 22, "income": 4000, "loan_amount": 15000, "job": "طالب", "finance_type": "تشاركي", "date": "05/04/2025"},
            ]
            for c in MOCK_DATA:
                c['risk_prob'] = predict_client_risk(c)
                c['risk_level'] = get_risk_level(c['risk_prob'])
                cursor.execute("INSERT OR REPLACE INTO clients (id, data) VALUES (?, ?)", (c['id'], json.dumps(c)))
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error seeding SQLite: {e}")

init_db()

# Login Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ===================== الصفحات =====================

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Hardcoded admin fallback
        if username == 'admin' and password == 'admin123':
            session['logged_in'] = True
            session['username'] = 'المسؤول'
            return redirect(url_for('dashboard'))
            
        user = get_user(username)
        if user and user.get('password') == password:
            session['logged_in'] = True
            session['username'] = user.get('full_name', username)
            return redirect(url_for('dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
        
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        username = request.form.get('username')
        password = request.form.get('password')
        
        if get_user(username) or username == 'admin':
            flash('اسم المستخدم موجود مسبقاً، يرجى اختيار اسم آخر', 'error')
        else:
            if save_user(username, password, full_name):
                flash('تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول', 'success')
                return redirect(url_for('login'))
            else:
                flash('حدث خطأ أثناء إنشاء الحساب، تأكد من الاتصال بقاعدة البيانات', 'error')
                
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    clients_list = get_all_clients()
    total = len(clients_list)
    low = sum(1 for c in clients_list if c.get('risk_level') == 'منخفض')
    mid = sum(1 for c in clients_list if c.get('risk_level') == 'متوسط')
    high = sum(1 for c in clients_list if c.get('risk_level') == 'مرتفع')
    
    stats = {
        'total': total,
        'low': low,
        'mid': mid,
        'high': high,
        'low_pct': round((low/total)*100, 1) if total else 0,
        'mid_pct': round((mid/total)*100, 1) if total else 0,
        'high_pct': round((high/total)*100, 1) if total else 0,
    }
    date_str = datetime.now().strftime("%d %B %Y")
    return render_template('dashboard.html', stats=stats, date=date_str)

@app.route('/clients')
@login_required
def clients():
    date_str = datetime.now().strftime("%d %B %Y")
    
    # Filtering
    search = request.args.get('search', '').lower()
    risk_filter = request.args.get('risk', 'الكل')
    type_filter = request.args.get('type', 'الكل')
    page = int(request.args.get('page', 1))
    
    clients_list = get_all_clients()
    
    filtered_clients = clients_list
    if search:
        filtered_clients = [c for c in filtered_clients if search in c['id'].lower() or search in c.get('job', '').lower()]
    if risk_filter != 'الكل':
        filtered_clients = [c for c in filtered_clients if c.get('risk_level') == risk_filter]
    if type_filter != 'الكل':
        filtered_clients = [c for c in filtered_clients if c.get('finance_type') == type_filter]
        
    total = len(clients_list)
    low = sum(1 for c in clients_list if c.get('risk_level') == 'منخفض')
    mid = sum(1 for c in clients_list if c.get('risk_level') == 'متوسط')
    high = sum(1 for c in clients_list if c.get('risk_level') == 'مرتفع')
    stats = {
        'total': total, 'low': low, 'mid': mid, 'high': high,
        'low_pct': round((low/total)*100, 1) if total else 0,
        'mid_pct': round((mid/total)*100, 1) if total else 0,
        'high_pct': round((high/total)*100, 1) if total else 0,
    }
    
    # Pagination
    per_page = 5
    total_pages = max(1, (len(filtered_clients) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_clients = filtered_clients[start_idx:end_idx]
    
    return render_template('clients.html', clients=paginated_clients, stats=stats, date=date_str, 
                           current_page=page, total_pages=total_pages, search=search, risk=risk_filter, type=type_filter)

def generate_new_client_id(clients_list):
    year = datetime.now().strftime('%Y')
    prefix = f"CLT-{year}-0"
    max_num = 0
    for c in clients_list:
        cid = c.get('id', '')
        if cid.startswith(prefix):
            try:
                num = int(cid.split('-')[-1])
                if num > max_num:
                    max_num = num
            except:
                pass
    new_num = max_num + 1 if max_num > 0 else 1
    return f"CLT-{year}-{new_num:06d}"

@app.route('/clients/add', methods=['POST'])
@login_required
def add_client():
    clients_list = get_all_clients()
    new_id = generate_new_client_id(clients_list)
    client = {
        "id": new_id,
        "name": request.form.get('name', 'عميل جديد'),
        "age": int(request.form.get('age', 30)),
        "income": float(request.form.get('income', 5000)),
        "loan_amount": float(request.form.get('loan_amount', 20000)),
        "job": request.form.get('job', 'أخرى'),
        "finance_type": request.form.get('finance_type', 'تقليدي'),
        "date": datetime.now().strftime("%d/%m/%Y")
    }
    client['risk_prob'] = predict_client_risk(client)
    client['risk_level'] = get_risk_level(client['risk_prob'])
    save_client(client)
    flash('تم إضافة العميل بنجاح!', 'success')
    return redirect(url_for('clients'))

@app.route('/clients/edit/<client_id>', methods=['GET', 'POST'])
@login_required
def edit_client_route(client_id):
    client = get_client(client_id)
    if not client:
        flash('العميل غير موجود', 'error')
        return redirect(url_for('clients'))
    
    if request.method == 'POST':
        new_id = request.form.get('id', client_id).strip()
        if new_id != client_id:
            # Check if new ID already exists
            if get_client(new_id):
                flash('معرف العميل الجديد مستخدم بالفعل', 'error')
                return redirect(url_for('edit_client_route', client_id=client_id))
            # Delete old record
            delete_client(client_id)
            client['id'] = new_id
            
        client['name'] = request.form.get('name', client.get('name', 'عميل جديد'))
        client['age'] = int(request.form.get('age', client.get('age', 30)))
        client['income'] = float(request.form.get('income', client.get('income', 0)))
        client['loan_amount'] = float(request.form.get('loan_amount', client.get('loan_amount', 0)))
        client['job'] = request.form.get('job', client.get('job', ''))
        client['finance_type'] = request.form.get('finance_type', client.get('finance_type', 'تقليدي'))
        
        # Calculate new risk probability
        prob = predict_client_risk(client)
        client['risk_prob'] = prob
        client['risk_level'] = get_risk_level(prob)
        
        save_client(client)
        flash('تم تعديل بيانات العميل بنجاح!', 'success')
        return redirect(url_for('clients'))
        
    return render_template('edit_client.html', client=client)

@app.route('/clients/delete/<client_id>', methods=['POST'])
@login_required
def delete_client_route(client_id):
    if delete_client(client_id):
        flash('تم حذف العميل بنجاح!', 'success')
    else:
        flash('حدث خطأ أثناء حذف العميل', 'error')
    return redirect(url_for('clients'))

@app.route('/risk_assessment')
@login_required
def risk_assessment():
    clients_list = get_all_clients()
    if not clients_list: return "لا يوجد عملاء", 404
    return risk_assessment_client(clients_list[0]['id'])

@app.route('/risk_assessment/<client_id>')
@login_required
def risk_assessment_client(client_id):
    clients_list = get_all_clients()
    client = get_client(client_id)
    if not client: return "العميل غير موجود", 404
        
    prob = client.get('risk_prob', 0)
    risk_level = client.get('risk_level', 'غير محدد')
    conv_decision = conventional_decision(prob)
    part_decision = participative_decision(prob)
    
    return render_template('risk_assessment.html', client=client, prob=prob, risk_level=risk_level, 
                           conv_decision=conv_decision, part_decision=part_decision, clients_list=clients_list)

@app.route('/sharia_compliance')
@login_required
def sharia_compliance():
    client_id = request.args.get('client_id')
    clients_list = get_all_clients()
    if not client_id and clients_list:
        client_id = clients_list[0]['id']
        
    client = get_client(client_id) if client_id else None
    if not client: return "العميل غير موجود", 404
    
    # Dynamic Sharia rules
    base_score = 100
    if client.get('finance_type') == 'تقليدي': 
        base_score -= 60
    
    if client.get('risk_level') == 'مرتفع': 
        base_score -= 30
    elif client.get('risk_level') == 'متوسط': 
        base_score -= 15
    
    score = min(100, max(0, base_score))
    status = "مطابق" if score >= 85 else ("مطابق جزئياً" if score >= 60 else "غير مطابق")
    
    return render_template('sharia_compliance.html', client=client, score=score, status=status, clients=clients_list)

@app.route('/sharia_compliance/export')
@login_required
def sharia_export():
    client_id = request.args.get('client_id')
    client = get_client(client_id) if client_id else None
    if not client: return "العميل غير موجود", 404
    
    content = f"تقرير الامتثال الشرعي\n"
    content += f"========================\n"
    content += f"تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    content += f"معرف العميل: {client['id']}\n"
    content += f"الدخل: {client['income']} درهم\n"
    content += f"المبلغ المطلوب: {client['loan_amount']} درهم\n"
    content += f"مستوى الخطر الائتماني: {client.get('risk_level', 'غير محدد')}\n"
    content += f"نوع التمويل المفضل: {client.get('finance_type', 'غير محدد')}\n\n"
    content += "النتيجة: تم تقييم المعايير الشرعية بناء على معايير AAOIFI. هذا التقرير هو نتيجة النظام الآلي.\n"
    
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-disposition": f"attachment; filename=sharia_report_{client['id']}.txt"}
    )

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', settings=GLOBAL_SETTINGS)

@app.route('/settings/update', methods=['POST'])
@login_required
def update_settings():
    form_type = request.form.get('form_type')
    
    if form_type == 'general':
        GLOBAL_SETTINGS['language'] = request.form.get('language', GLOBAL_SETTINGS['language'])
        GLOBAL_SETTINGS['currency'] = request.form.get('currency', GLOBAL_SETTINGS['currency'])
        GLOBAL_SETTINGS['timezone'] = request.form.get('timezone', GLOBAL_SETTINGS['timezone'])
        GLOBAL_SETTINGS['display_mode'] = request.form.get('display_mode', GLOBAL_SETTINGS['display_mode'])
        GLOBAL_SETTINGS['results_per_page'] = int(request.form.get('results_per_page', GLOBAL_SETTINGS['results_per_page']))
        GLOBAL_SETTINGS['session_timeout'] = int(request.form.get('session_timeout', GLOBAL_SETTINGS['session_timeout']))
        flash('تم حفظ الإعدادات العامة بنجاح!', 'success')
        
    elif form_type == 'sharia':
        GLOBAL_SETTINGS['sharia_enabled'] = 'sharia_enabled' in request.form
        GLOBAL_SETTINGS['sharia_source'] = request.form.get('sharia_source', GLOBAL_SETTINGS['sharia_source'])
        GLOBAL_SETTINGS['sharia_update'] = datetime.now().strftime("%d/%m/%Y")
        flash('تم حفظ المعايير الشرعية بنجاح!', 'success')
        
    return redirect(url_for('settings'))

@app.route('/models')
@login_required
def models():
    return render_template('models.html', feature_names=feature_names, model_loaded=(model is not None))

@app.route('/reports')
@login_required
def reports():
    clients_list = get_all_clients()
    total = len(clients_list)
    trad = sum(1 for c in clients_list if c.get('finance_type') == 'تقليدي')
    part = sum(1 for c in clients_list if c.get('finance_type') == 'تشاركي')
    return render_template('reports.html', total=total, trad=trad, part=part, clients=clients_list)


# ===================== الميزات الجديدة: البحث التاريخي والإحصائيات المتقدمة =====================

@app.route('/historical_search')
@login_required
def historical_search():
    """صفحة البحث التاريخي في بيانات raw_data.csv"""
    result = None
    search_id = request.args.get('sk_id', '').strip()
    error = None
    
    if search_id and RAW_DATA is not None:
        try:
            # Compare strings directly or cast to int if numeric
            search_val = int(search_id)
            row = RAW_DATA[RAW_DATA['SK_ID_CURR'] == search_val]
            if len(row) > 0:
                row_dict = row.iloc[0].to_dict()
                # تنظيف القيم: تحويل NaN إلى "غير متوفر"
                clean_result = {}
                for k, v in row_dict.items():
                    if k == 'DAYS_BIRTH' and pd.notna(v):
                        clean_result['DAYS_BIRTH'] = v
                        clean_result['العمر (تقريبي)'] = f"{int(abs(v)/365)} سنة"
                    elif pd.isna(v):
                        clean_result[k] = "غير متوفر"
                    else:
                        clean_result[k] = v
                result = clean_result
            else:
                error = f"لم يتم العثور على عميل برقم {search_id}"
        except Exception as e:
            error = f"حدث خطأ أثناء البحث: {e}"
    elif search_id and RAW_DATA is None:
        error = "ملف البيانات التاريخية غير متوفر"
    
    # أخذ عينة من أرقام العملاء للعرض
    sample_ids = []
    if RAW_DATA is not None and 'SK_ID_CURR' in RAW_DATA.columns:
        sample_ids = RAW_DATA['SK_ID_CURR'].head(10).tolist()
    
    return render_template('historical_search.html', result=result, search_id=search_id, 
                           error=error, sample_ids=sample_ids, data_loaded=(RAW_DATA is not None),
                           total_records=len(RAW_DATA) if RAW_DATA is not None else 0)

@app.route('/import_historical/<client_id>')
@login_required
def import_historical(client_id):
    """استيراد عميل من البيانات التاريخية إلى العملاء الحاليين"""
    if RAW_DATA is None:
        flash("البيانات التاريخية غير متوفرة", "error")
        return redirect(url_for('historical_search'))
        
    try:
        search_val = int(client_id)
        row = RAW_DATA[RAW_DATA['SK_ID_CURR'] == search_val]
        if len(row) > 0:
            row_dict = row.iloc[0].to_dict()
            
            # استخراج و تنظيف البيانات
            age = int(-row_dict.get('DAYS_BIRTH', 0) / 365) if not pd.isna(row_dict.get('DAYS_BIRTH')) else 30
            income = row_dict.get('AMT_INCOME_TOTAL', 0)
            loan_amount = row_dict.get('AMT_CREDIT', 0)
            job = row_dict.get('OCCUPATION_TYPE', 'غير محدد')
            if pd.isna(job): job = 'غير محدد'
            finance_type = 'تقليدي' if row_dict.get('NAME_CONTRACT_TYPE') == 'Cash loans' else 'تشاركي'
            
            new_client = {
                'id': f"CLT-{datetime.now().strftime('%Y')}-{search_val:06d}",
                'name': f"عميل تاريخي {search_val}",
                'age': age,
                'income': income,
                'loan_amount': loan_amount,
                'job': job,
                'finance_type': finance_type,
                'date': datetime.now().strftime("%d/%m/%Y")
            }
            
            # حساب الخطر بالاعتماد على كامل بيانات العميل التاريخية
            new_client['risk_prob'] = predict_client_risk(new_client, historical_data=row_dict)
            new_client['risk_level'] = get_risk_level(new_client['risk_prob'])
            
            # حفظ العميل
            save_client(new_client)
            
            flash(f"تم استيراد العميل بنجاح إلى قاعدة البيانات السحابية بالمعرف الجديد {new_client['id']}", "success")
            return redirect(url_for('clients'))
        else:
            flash("لم يتم العثور على العميل في السجلات التاريخية", "error")
            return redirect(url_for('historical_search'))
    except Exception as e:
        flash(f"حدث خطأ أثناء الاستيراد: {e}", "error")
        return redirect(url_for('historical_search'))

@app.route('/analytics')
@login_required
def analytics():
    """لوحة الإحصائيات المتقدمة لملف raw_data.csv"""
    return render_template('analytics.html', stats=RAW_DATA_STATS, data_loaded=(RAW_DATA is not None))

@app.route('/api/analytics_data')
@login_required
def analytics_data():
    """API لجلب بيانات الإحصائيات للرسوم البيانية"""
    return jsonify(RAW_DATA_STATS)


@app.route('/debug_db')
def debug_db():
    info = {
        'USE_FIREBASE': USE_FIREBASE,
        'db_initialized': db is not None,
        'os_environ_PYTHONANYWHERE_SITE': 'PYTHONANYWHERE_SITE' in os.environ,
        'smart_finance_db_exists': os.path.exists(DB_FILE),
        'sqlite_clients_count': 0,
        'sqlite_users_count': 0,
        'sqlite_error': None
    }
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM clients")
        info['sqlite_clients_count'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        info['sqlite_users_count'] = cursor.fetchone()[0]
        conn.close()
    except Exception as e:
        info['sqlite_error'] = str(e)
    return jsonify(info)


if __name__ == '__main__':
    app.run(debug=True, port=5050)