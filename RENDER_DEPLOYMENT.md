# Deployment Guide for Render

## Database Setup on Render

1. **Create a PostgreSQL Database**
   - In Render dashboard, go to "New +" → "PostgreSQL"
   - Name: `result-management-db`
   - Keep default settings
   - Copy the database URL (looks like: `postgresql://user:password@host/dbname`)

2. **Add Environment Variable**
   - In your Web Service settings, add:
     - Key: `DATABASE_URL`
     - Value: Paste the PostgreSQL URL from step 1

3. **Your app will use this persistent database**
   - Data survives service restarts
   - Free tier is generous for small projects

## Current SQLite Limitation

The current setup uses SQLite which:
- ❌ Does NOT persist on Render free tier
- ❌ Is lost every time the service restarts
- ❌ Only suitable for local development

## Migration Path

To migrate from SQLite to PostgreSQL:
1. Install `psycopg2-binary` in requirements.txt
2. Modify `app.py` to use SQLAlchemy with PostgreSQL
3. Export current data and import to PostgreSQL

We can help with this if needed!
