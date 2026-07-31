import app
import json

clients = app.get_all_clients()
data = []
for c in clients:
    data.append({
        'id': c.get('id'),
        'risk_prob': c.get('risk_prob'),
        'risk_level': c.get('risk_level')
    })
    
with open('debug_clients.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("Done")
