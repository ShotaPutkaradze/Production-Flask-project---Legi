from sqlalchemy import text
from app import app, db

# ახალი სვეტების სია, რომლებიც უნდა დაემატოს
columns_to_add = {
    "uc_padoni": "INTEGER",
    "uc_ryadi": "INTEGER"
}

with app.app_context():
    for column_name, column_type in columns_to_add.items():
        try:
            # SQL ბრძანება სვეტის დასამატებლად, თუ ის არ არსებობს
            sql_command = text(f"ALTER TABLE results ADD COLUMN IF NOT EXISTS {column_name} {column_type};")
            db.session.execute(sql_command)
            print(f"✅ Column '{column_name}' checked/added to 'results' table.")
        except Exception as e:
            print(f"❌ Error adding column '{column_name}': {e}")
    
    try:
        db.session.commit()
        print("✅ Database changes committed successfully.")
    except Exception as e:
        print(f"❌ Error committing changes: {e}")

