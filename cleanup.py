import app
clients = app.get_all_clients()
for c in clients:
    if not c['id'].startswith('CLT-2025'):
        app.delete_client(c['id'])
        print(f"Deleted old client {c['id']}")
print("Cleanup done.")
