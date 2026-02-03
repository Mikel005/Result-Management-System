import sqlite3
import os

DATABASE = 'results.db'

def test_routes_logic():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    print("Testing registration management logic...")
    
    # Check if a student has registrations
    student_id = 'STU001' # Assuming this exists from previous tests or common sample
    c.execute("SELECT * FROM students WHERE student_id=?", (student_id,))
    student = c.fetchone()
    if not student:
        # Create a dummy student for testing if not exists
        c.execute("INSERT OR IGNORE INTO students (student_id, name, class) VALUES (?, ?, ?)", 
                  (student_id, 'Test Student', 'Class A'))
        conn.commit()
    
    # Check offerings
    c.execute("SELECT id FROM course_offerings LIMIT 1")
    offering = c.fetchone()
    if not offering:
        print("No offerings found. Please create an offering first.")
        return

    offering_id = offering['id']
    
    # 1. Test registration
    try:
        c.execute("INSERT OR IGNORE INTO course_registrations (student_id, offering_id) VALUES (?, ?)", 
                  (student_id, offering_id))
        conn.commit()
        print(f"Successfully registered student {student_id} for offering {offering_id}")
    except Exception as e:
        print(f"Registration failed: {e}")
        
    # 2. Verify registration exists (Admin/Student view logic)
    c.execute("SELECT * FROM course_registrations WHERE student_id=?", (student_id,))
    reg = c.fetchone()
    if reg:
        print("Verification: Registration found in database.")
    else:
        print("Verification: Registration NOT found in database.")
        
    # 3. Test deletion (Admin logic)
    if reg:
        reg_id = reg['id']
        c.execute("DELETE FROM course_registrations WHERE id=?", (reg_id,))
        conn.commit()
        print(f"Successfully deleted registration {reg_id}")
        
        # Verify deletion
        c.execute("SELECT * FROM course_registrations WHERE id=?", (reg_id,))
        if not c.fetchone():
            print("Verification: Registration successfully removed from database.")
        else:
            print("Verification: Registration STILL EXISTS in database.")

    conn.close()

if __name__ == "__main__":
    if os.path.exists(DATABASE):
        test_routes_logic()
    else:
        print(f"Database {DATABASE} not found.")
