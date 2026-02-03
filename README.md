# Result Management System

A modern, comprehensive web-based platform for managing academic results, course registrations, and student performance insights. Built with Flask, SQLite, and a premium card-based UI.

## 🚀 Features

### 👤 Admin Portal
- **Dashboard**: High-level statistics on students, subjects, results, and users.
- **Academic Management**: Full CRUD for Faculties, Departments, Classes, and Subjects.
- **Course Offerings**: Create and manage course offerings for specific sessions and semesters.
- **Result Management**: Add, approve, amend, and delete academic results.
- **User Management**: Role-based access control (Admin, Teacher, Student).
- **Import/Export**: Bulk results management via CSV.
- **Audit Logs**: Track system-wide activities for accountability.

### 👨‍🏫 Teacher Portal
- **Dashboard**: View assigned course offerings for current and past sessions.
- **Grading Interface**: Modern grid-based grading system allowing detailed score breakdowns (Assignment, Tests, Exams).
- **Class Lists**: Automated fetching of students registered for assigned subjects.

### 🎓 Student Portal
- **Self-Registration**: Easy onboarding and login.
- **Course Registration**: Filter and register for available offerings per session.
- **Academic Transcript**: A premium, printable transcript view showing detailed marks, score breakdowns, and color-coded grades.
- **Performance Overview**: Quick stats on average marks and enrolled subjects.

### 🧠 AI Insights
- **Performance Prediction**: Predict student performance based on historical data.
- **Risk Analysis**: Identify at-risk students who may need additional support.
- **Personalized Recommendations**: AI-generated study advice.
- **Anomalies**: Detect unusual patterns in grading and performance.

## 🛠️ Technology Stack
- **Backend**: Python / Flask
- **Database**: SQLite
- **Frontend**: HTML5, Vanilla CSS3 (Modern/Glassmorphism aesthetic), FontAwesome Icons
- **AI**: Custom AI Engine (`ai_engine.py`)
- **Security**: Role-based decorators, CSRF protection, salted password hashing

## 📦 File Structure
- `app.py`: Main application logic and routes.
- `ai_engine.py`: AI-driven analysis and insights logic.
- `utils.py`: Helper functions (grading logic, email notifications).
- `results.db`: SQLite database file.
- `static/`: CSS and client-side assets.
- `templates/`: HTML templates for all portals.

## ⚙️ Setup & Installation
1. Install dependencies: `pip install -r requirements.txt`
2. Initialize database: `python app.py` (automatically runs `init_db`)
3. Run the application: `python app.py` 
4. Access at: `http://127.0.0.1:5000`

---
*Created with focus on Excellence in Education Management.*
