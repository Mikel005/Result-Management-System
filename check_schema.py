
import sqlite3
import os

def check_db():
    with open('schema_results.txt', 'w') as f:
        f.write("--- Starting database check ---\n")
        db_file = 'results.db'
        if not os.path.exists(db_file):
            f.write(f"ERROR: {db_file} not found!\n")
            return
            
        f.write(f"Found {db_file}, size: {os.path.getsize(db_file)} bytes\n")
        
        try:
            conn = sqlite3.connect(db_file)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            f.write("\n--- SUBJECTS TABLE ---\n")
            c.execute("PRAGMA table_info(subjects)")
            rows = c.fetchall()
            for row in rows:
                f.write(f"{row['name']} ({row['type']})\n")
                
            f.write("\n--- RESULTS TABLE ---\n")
            c.execute("PRAGMA table_info(results)")
            rows = c.fetchall()
            for row in rows:
                f.write(f"{row['name']} ({row['type']})\n")
            
            conn.close()
        except Exception as e:
            f.write(f"EXCEPTION: {str(e)}\n")
        f.write("--- Script finished ---\n")

if __name__ == "__main__":
    check_db()
