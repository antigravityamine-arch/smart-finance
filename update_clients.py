import app
clients = app.get_all_clients()
for c in clients:
    # Recalculate using fixed model
    new_prob = app.predict_client_risk(c)
    new_level = app.get_risk_level(new_prob)
    app.update_client(c['id'], {'risk_prob': new_prob, 'risk_level': new_level})
print("Updated all clients successfully")
