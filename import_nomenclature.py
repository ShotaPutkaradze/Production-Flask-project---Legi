import pandas as pd
from app import app, db
from models import Nomenclature
import sys

def import_data():
    # Set default encoding for stdout to handle unicode characters in prints
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')

    with app.app_context():
        # --- ცხრილის გასუფთავება, რათა თავიდან ავიცილოთ დუბლიკატები ---
        try:
            db.session.query(Nomenclature).delete()
            db.session.commit()
            print("✅ Old nomenclature data cleared.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Could not clear old data: {e}")
            return

        # --- CSV ფაილის წაკითხვა ---
        try:
            df = pd.read_csv("nomenclature.csv", encoding='utf-8-sig')
            df.columns = [col.strip() for col in df.columns]
            print(f"✅ Found {len(df)} total rows in nomenclature.csv.")
        except FileNotFoundError:
            print("❌ nomenclature.csv not found. Aborting.")
            return
        
        # --- დუბლიკატების შემოწმება არტიკულის მიხედვით ---
        df.drop_duplicates(subset=['Артикул'], keep='first', inplace=True)
        print(f"ℹ️ Found {len(df)} unique rows to import after dropping duplicates by 'Артикул'.")

        # --- მონაცემების დამატება ბაზაში ---
        try:
            for index, row in df.iterrows():
                new_item = Nomenclature(
                    zavod=str(row.get('Завод', '')).strip(),
                    storona=str(row.get('Сторона', '')).strip(),
                    v_gruppe=str(row.get('В Группе', '')).strip(),
                    kategoriya=str(row.get('Категория', '')).strip(),
                    naimenovanie=str(row.get('Наименование', '')).strip(),
                    artikul=str(row.get('Артикул', '')).strip()
                )
                db.session.add(new_item)
            
            db.session.commit()
            print(f"✅ Successfully imported {len(df)} unique items into the database.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ An error occurred during import: {e}")

if __name__ == "__main__":
    import_data()
