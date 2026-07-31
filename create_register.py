import os

with open('templates/login.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('سجل الدخول للوصول إلى حسابك', 'قم بإنشاء حساب جديد للوصول إلى المنصة')
content = content.replace('تسجيل الدخول', 'إنشاء حساب')
content = content.replace('<div class="options">', '<div class="options" style="display:none;">')
content = content.replace('url_for(\'register\')', 'url_for(\'login\')')
content = content.replace('action="/"', 'action="/register"')
content = content.replace('👥 إنشاء حساب جديد', 'تسجيل الدخول لحساب موجود')

new_input = '''<div class="form-group">
                <label>🧑 الاسم الكامل</label>
                <input type="text" name="full_name" placeholder="أدخل اسمك الكامل" required>
            </div>
            <div class="form-group">
                <label>👤 اسم المستخدم</label>'''

content = content.replace('<div class="form-group">\n                <label>👤 اسم المستخدم</label>', new_input)

with open('templates/register.html', 'w', encoding='utf-8') as f:
    f.write(content)
