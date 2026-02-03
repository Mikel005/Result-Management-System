from app import init_db

print("Running database migrations...")
try:
    init_db()
    print("Migrations completed successfully.")
except Exception as e:
    print(f"Error running migrations: {e}")
