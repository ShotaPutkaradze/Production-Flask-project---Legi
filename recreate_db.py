from app import app, db
from sqlalchemy import text

def recreate_database():
    with app.app_context():
        print("Starting database recreation...")
        
        # --- Drop tables in the correct order to respect foreign keys ---
        try:
            # We use raw SQL to drop tables to avoid any ORM-level issues
            db.session.execute(text('DROP TABLE IF EXISTS edit_history CASCADE;'))
            db.session.execute(text('DROP TABLE IF EXISTS results CASCADE;'))
            db.session.execute(text('DROP TABLE IF EXISTS nomenclature CASCADE;'))
            db.session.commit()
            print("✅ Successfully dropped old tables.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ An error occurred while dropping tables: {e}")
            return

        # --- Recreate all tables based on the current models.py ---
        try:
            db.create_all()
            db.session.commit()
            print("✅ Successfully created all tables based on current models.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ An error occurred during table creation: {e}")

if __name__ == "__main__":
    recreate_database()
