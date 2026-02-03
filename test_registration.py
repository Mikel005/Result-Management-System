
import sqlite3
from app import app, get_db

def test_registration():
    with app.app_context():
        db = get_db()
        c = db.cursor()
        
        # 1. Setup: Ensure a student and an offering exist
        student_id = "TEST_STU_001"
        c.execute("INSERT OR IGNORE INTO students (student_id, name, class) VALUES (?, ?, ?)", (student_id, "Test Student", "JSS1"))
        
        c.execute("INSERT OR IGNORE INTO subjects (subject_code, subject_name, class_id) VALUES (?, ?, ?)", ("TEST101", "Test Subject", 1))
        
        c.execute("INSERT OR IGNORE INTO course_offerings (subject_code, semester, academic_year, teacher_id) VALUES (?, ?, ?, ?)", ("TEST101", "1st", "2024/2025", None))
        offering_id = c.lastrowid
        if offering_id == 0: # Already existed, fetch it
            c.execute("SELECT id FROM course_offerings WHERE subject_code='TEST101'")
            offering_id = c.fetchone()['id']
            
        print(f"Testing registration regarding Offering ID: {offering_id} for Student: {student_id}")

        # 2. Simulate POST request logic directly (bypassing Client/HTTP to test logic first)
        selected = [str(offering_id)]
        
        # Cleanup previous reg if any
        c.execute("DELETE FROM course_registrations WHERE student_id=? AND offering_id=?", (student_id, offering_id))
        db.commit()
        
        # -- LOGIC FROM app.py --
        successful = []
        already = []
        
        c.execute("SELECT offering_id FROM course_registrations WHERE student_id=?", (student_id,))
        current_regs = {row['offering_id'] for row in c.fetchall()}
        
        for oid in selected:
            oid_i = int(oid)
            
            if oid_i in current_regs:
                already.append(oid_i)
                continue
                
            try:
                c.execute("INSERT INTO course_registrations (offering_id, student_id) VALUES (?, ?)", (oid_i, student_id))
                successful.append(oid_i)
            except sqlite3.IntegrityError:
                already.append(oid_i)
            except sqlite3.Error as e:
                print(f"DB Error: {e}")
        
        db.commit()
        
        if successful:
            print(f"SUCCESS: Registered for {successful}")
        elif already:
            print(f"INFO: Already registered")
        else:
            print("FAILURE: No registration happened")

        # Verify DB
        c.execute("SELECT * FROM course_registrations WHERE student_id=? AND offering_id=?", (student_id, offering_id))
        if c.fetchone():
            print("VERIFIED: Record exists in DB")
        else:
            print("VERIFIED: Record MISSING in DB")

if __name__ == "__main__":
    test_registration()
