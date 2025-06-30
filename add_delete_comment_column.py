from sqlalchemy import text
from app import app, db

with app.app_context():
    db.session.execute(text("ALTER TABLE results ADD COLUMN IF NOT EXISTS delete_comment TEXT;"))
    db.session.commit()
    print("✅ Column 'delete_comment' added to 'results' table.")
