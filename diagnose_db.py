import sqlite3
import os

DATABASE = 'results.db'

def diagnose():
    if not os.path.exists(DATABASE):
        print(f"Error: {DATABASE} not found.")
        return

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    print("--- User Accounts ---")
    c.execute("SELECT id, username, role, email FROM users")
    users = c.fetchall()
    for user in users:
        print(f"ID: {user['id']}, Username: '{user['username']}', Role: '{user['role']}', Email: '{user['email']}'")
    
    print("\n--- Students Table (Partial) ---")
    c.execute("SELECT student_id, name, pin FROM students LIMIT 5")
    students = c.fetchall()
    for s in students:
        has_pin = "Yes" if s['pin'] else "No"
        print(f"ID: {s['student_id']}, Name: {s['name']}, Has PIN: {has_pin}")

    conn.close()

if __name__ == "__main__":
    diagnose()
