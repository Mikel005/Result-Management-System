
import sqlite3

def check_results():
    conn = sqlite3.connect('results.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    with open('result_data_check.txt', 'w') as f:
        c.execute("SELECT status, COUNT(*) as cnt FROM results GROUP BY status")
        rows = c.fetchall()
        f.write("--- STATUS COUNTS ---\n")
        for row in rows:
            f.write(f"{row['status']}: {row['cnt']}\n")
            
        c.execute("SELECT r.*, s.name FROM results r JOIN students s ON r.student_id = s.student_id LIMIT 10")
        rows = c.fetchall()
        f.write("\n--- RECENT RESULTS ---\n")
        for row in rows:
            f.write(f"Student: {row['name']} ({row['student_id']}), Sub: {row['subject_code']}, Marks: {row['marks']}, Status: {row['status']}\n")

    conn.close()

if __name__ == "__main__":
    check_results()
