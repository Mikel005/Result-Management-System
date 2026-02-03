import sqlite3

DATABASE = 'results.db'

def check_users():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    print("Checking users table...")
    c.execute("SELECT id, username, role, email FROM users")
    users = c.fetchall()
    
    if not users:
        print("No users found in the database.")
    else:
        print(f"Found {len(users)} user(s):")
        for user in users:
            print(f"ID: {user['id']}, Username: {user['username']}, Role: {user['role']}, Email: {user['email']}")
            
    conn.close()

if __name__ == "__main__":
    check_users()
