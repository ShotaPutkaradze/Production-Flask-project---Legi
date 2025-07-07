# app.py

# --- Core Imports ---
from flask import Flask, render_template, request, make_response, session, url_for, flash, redirect
# db ობიექტი შემოგვაქვს models.py-დან
from models import db, Result, EditHistory, Nomenclature
import pandas as pd
import os
import re 
import io
import csv
import logging
import secrets
from logging.handlers import RotatingFileHandler
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, func, cast, Date
from datetime import datetime, timedelta 

from flask_migrate import Migrate 

# === 1. FLASK APP SETUP ===
# Initialize the Flask application
app = Flask(__name__)
# Load configuration from the config.py file
app.config.from_object('config')

# Initialize the database and migration tool with the app
# db ობიექტს, რომელიც შემოვიტანეთ models.py-დან, ვუკავშირებთ ჩვენს აპლიკაციას
db.init_app(app)
# migrate ობიექტს ვუკავშირებთ იგივე აპლიკაციას და db-ს
migrate = Migrate(app, db)

# === 2. LOGGING SETUP ===
# Ensure the 'logs' directory exists
os.makedirs('logs', exist_ok=True)
# Configure rotating file handler to limit log file size
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
file_handler.setLevel(logging.INFO) 
app.logger.setLevel(logging.INFO)
# Define the format for log messages
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
app.logger.addHandler(file_handler)


# === 3. INITIAL DATA LOADING ===
# This block runs once when the application starts
with app.app_context():
    # Create all database tables based on models.py if they don't exist
    db.create_all()

    # Load operator credentials from operators.csv
    try:
        operators_df = pd.read_csv('operators.csv', encoding='utf-8-sig')
        credentials = {}
        for _, row in operators_df.iterrows():
            credentials[row["username"]] = {
                "password": str(row["password"]),
                "Завод": row["Завод"]
            }
        operator_factories = dict(zip(operators_df['username'], operators_df['Завод']))
        app.logger.info("✅ Operators.csv loaded successfully.")
    except FileNotFoundError:
        credentials = {}
        app.logger.error("❌ FATAL: operators.csv not found.")

    # Load nomenclature data from the database to create an Artikuls map
    name_to_artikul = {}
    try:
        nomen_items = Nomenclature.query.all()
        name_to_artikul = {item.naimenovanie: item.artikul for item in nomen_items}
        app.logger.info(f"✅ Successfully loaded {len(nomen_items)} items from Nomenclature table.")
    except Exception as e:
        app.logger.error(f"❌ Could not load data from Nomenclature table: {e}")


# === 4. UTILITY FUNCTIONS ===
def natural_sort_key(s):
    """
    Sorts strings containing numbers in a human-friendly way (e.g., 4cm, 8cm, 10cm).
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def get_unique(column, **filters):
    """
    Queries the Nomenclature table to get unique, sorted values from a specific column,
    based on the provided filters.
    """
    query = db.session.query(getattr(Nomenclature, column)).distinct()
    
    for col, val in filters.items():
        # The filter keys (e.g., 'zavod') are lowercase model attribute names
        if val:
            stripped_val = val.strip()
            query = query.filter(getattr(Nomenclature, col.lower()) == stripped_val)
            
    results = [r[0] for r in query.all()]
    sorted_results = sorted(results, key=natural_sort_key)
    return sorted_results

# === 5. ROUTES ===

@app.route("/", methods=["GET", "POST"])
def login():
    """
    Handles user login. On POST, it verifies credentials against the loaded data.
    On successful login, it stores user info in the session and redirects.
    """
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in credentials:
            if credentials[username]["password"] == str(password):
                session["user"] = username
                session["factory"] = credentials[username]["Завод"]

                if username == "admin":
                    return redirect(url_for("admin_history"))

                return redirect(url_for("select_side"))
            else:
                flash("❌ არასწორი პაროლი", "error")
        else:
            flash("❌ ოპერატორი არ მოიძებნა", "error")
    return render_template("login.html", operators=credentials.keys())


@app.route("/logout")
def logout():
    """
    Clears the session to log the user out and redirects to the login page.
    """
    session.clear()
    return redirect(url_for("login"))


@app.route("/report")
def report():
    """
    Generates and displays a report based on a date range and an optional operator filter.
    """
    if "user" not in session:
        return redirect(url_for("login"))
    
    # Get parameters from the URL
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    selected_operator = request.args.get('operator')
    
    totals = None
    results = []

    # Fetch all unique operators for the filter dropdown
    all_operators = [op[0] for op in db.session.query(Result.operator).distinct().order_by(Result.operator).all()]

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            # Add 1 day to the end_date to include all records from that day
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            
            # Base query for the date range
            query = Result.query.filter(
                Result.created_at >= start_date,
                Result.created_at < end_date
            )

            # Apply operator filter if one is selected
            if selected_operator:
                query = query.filter(Result.operator == selected_operator)
            
            results = query.order_by(Result.created_at.desc()).all()

            # --- Calculate totals in Python for robustness ---
            total_kolichestvo = 0
            total_gp_padoni = 0
            total_gp_ryadi = 0
            total_brak_padoni = 0
            total_brak_ryadi = 0
            total_uc_padoni = 0
            total_uc_ryadi = 0

            for r in results:
                try:
                    if r.kolichestvo and r.kolichestvo.strip():
                        total_kolichestvo += float(r.kolichestvo)
                except (ValueError, TypeError):
                    pass # Ignore if kolichestvo is not a valid number

                total_gp_padoni += r.gp_padoni or 0
                total_gp_ryadi += r.gp_ryadi or 0
                total_brak_padoni += r.brak_padoni or 0
                total_brak_ryadi += r.brak_ryadi or 0
                total_uc_padoni += r.uc_padoni or 0
                total_uc_ryadi += r.uc_ryadi or 0

            totals = {
                "total_kolichestvo": total_kolichestvo,
                "total_gp_padoni": total_gp_padoni,
                "total_gp_ryadi": total_gp_ryadi,
                "total_brak_padoni": total_brak_padoni,
                "total_brak_ryadi": total_brak_ryadi,
                "total_uc_padoni": total_uc_padoni,
                "total_uc_ryadi": total_uc_ryadi,
            }

        except ValueError:
            flash("არასწორი თარიღის ფორმატი. / Неверный формат даты.", "error")
            return redirect(url_for('report'))
        except Exception as e:
            app.logger.error(f"Error in /report route: {e}", exc_info=True)
            flash("რეპორტის გენერაციისას მოხდა შეცდომა. დეტალებისთვის იხილეთ ლოგ ფაილი.", "error")
            return redirect(url_for('report'))


    return render_template('report.html', 
                           start_date=start_date_str,
                           end_date=end_date_str,
                           selected_operator=selected_operator,
                           all_operators=all_operators,
                           totals=totals, 
                           results=results)


@app.route("/admin_history")
def admin_history():
    """
    Displays a paginated history of all records for the admin.
    """
    if session.get("user") != "admin":
        return redirect(url_for("login"))

    try:
        page = request.args.get("page", 1, type=int)
        per_page = 100

        pagination = Result.query.order_by(Result.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        results = pagination.items

        # Add 'artikul' to each result object for display
        for r in results:
            r.artikul = name_to_artikul.get(r.naimenovanie, "")

        FIELD_LABELS = {
            "kolichestvo": "Количество",
            "comment": "Комментарий",
            "gp_padoni": "Готовая продукция (Падони)",
            "gp_ryadi": "Готовая продукция (Ряди)",
            "brak_padoni": "Брак (Падони)",
            "brak_ryadi": "Брак (Ряди)",
            "uc_padoni": "Уцененная (Падони)",
            "uc_ryadi": "Уцененная (Ряди)",
        }

        return render_template(
            "admin_history.html",
            results=results,
            pagination=pagination,
            FIELD_LABELS=FIELD_LABELS,
        )

    except Exception as e:
        app.logger.error("Error fetching admin history:", exc_info=True)
        return f"❌ Error fetching history: {str(e)}", 500



@app.route("/operator_history")
def operator_history():
    """
    Displays a paginated history of records for the logged-in operator.
    """
    if "user" not in session or session["user"] == "admin":
        return redirect(url_for("login"))

    try:
        user = session["user"]
        page = request.args.get("page", 1, type=int)
        per_page = 100
        pagination = Result.query.filter_by(operator=user)\
            .order_by(Result.created_at.desc())\
            .paginate(page=page, per_page=per_page)

        results = pagination.items

        # Add 'artikul' to each result object
        for r in results:
            r.artikul = name_to_artikul.get(r.naimenovanie, "")

        FIELD_LABELS = {
            "kolichestvo": "Количество",
            "comment": "Комментарий",
            "gp_padoni": "Готовая продукция (Падони)",
            "gp_ryadi": "Готовая продукция (Ряди)",
            "brak_padoni": "Брак (Падони)",
            "brak_ryadi": "Брак (Ряди)",
            "uc_padoni": "Уцененная (Падони)",
            "uc_ryadi": "Уцененная (Ряди)",
        }

        return render_template(
            "operator_history.html",
            results=results, 
            pagination=pagination,
            operator=user,
            FIELD_LABELS=FIELD_LABELS
        )
    except Exception as e:
        app.logger.error("Error fetching operator history:", exc_info=True)
        return f"❌ Error fetching operator history: {str(e)}", 500



@app.route("/side", methods=["GET", "POST"])
def select_side():
    """
    First step of data entry: selecting the production side (wet/dry).
    """
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        factory = request.form.get("factory", "").strip()
        selected_side = request.form.get("side", "").strip()

        if factory:
            session["factory"] = factory
        if selected_side:
            session["side"] = selected_side
            return redirect(url_for("select_subgroup"))
    else:
        factory = session.get("factory")
        if not factory:
            return redirect(url_for("login"))

    operator = session.get("user")
    sides = get_unique("storona", zavod=factory)

    return render_template(
        "side.html",
        factory=factory,
        sides=sides,
        operator=operator
    )



@app.route("/subgroup", methods=["GET", "POST"])
def select_subgroup():
    """
    Second step: selecting the subgroup based on factory and side.
    """
    if request.method == "POST":
        session["factory"] = request.form.get("factory", "").strip()
        session["side"] = request.form.get("side", "").strip()
    
    factory = session.get("factory")
    side = session.get("side")
    if not all([factory, side]):
        return redirect(url_for("select_side"))

    if request.method == "POST":
        subgroup = request.form.get("subgroup")
        if subgroup:
            session["subgroup"] = subgroup
            return redirect(url_for("select_category"))
        
    subgroups = get_unique("v_gruppe", zavod=factory, storona=side)
    operator = session.get("user")
    selection_path = side

    return render_template(
        "subgroup.html",
        factory=factory,
        side=side,
        operator=operator,
        subgroups=subgroups,
        selection_path=selection_path
    )



@app.route("/category", methods=["GET", "POST"])
def select_category():
    """
    Third step: selecting the category based on previous selections.
    """
    if request.method == "POST":
        session["subgroup"] = request.form.get("subgroup", "").strip()

    factory = session.get("factory")
    side = session.get("side")
    subgroup = session.get("subgroup")

    if not all([factory, side, subgroup]):
        return redirect(url_for("select_subgroup"))

    if request.method == "POST":
        category = request.form.get("category")
        if category:
            session["category"] = category
            return redirect(url_for("select_product"))

    categories = get_unique("kategoriya", zavod=factory, storona=side, v_gruppe=subgroup)
    selection_path = f"{side} > {subgroup}"
    operator = session.get("user")

    return render_template(
        "category.html",
        factory=factory,
        side=side,
        subgroup=subgroup,
        categories=categories,
        selection_path=selection_path,
        operator=operator
    )


@app.route("/product", methods=["GET", "POST"])
def select_product():
    """
    Fourth step: selecting the product and entering quantities.
    """
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        session["category"] = request.form.get("category", "").strip()

    factory = session.get("factory")
    side = session.get("side")
    subgroup = session.get("subgroup")
    category = session.get("category")

    if not all([factory, side, subgroup, category]):
        return redirect(url_for("select_category"))

    products = get_unique("naimenovanie", zavod=factory, storona=side, v_gruppe=subgroup, kategoriya=category)
    operator = session.get("user")
    selection_path = f"{side} > {subgroup} > {category}"

    return render_template(
        "product.html",
        factory=factory,
        side=side,
        subgroup=subgroup,
        category=category,
        products=products,
        operator=operator,
        selection_path=selection_path
    )



@app.route("/submit", methods=["POST"])
def submit():
    """
    Final step: gathers all form data and saves it to the database.
    """
    side = request.form.get("side", "")

    data = {
        "Завод": request.form.get("factory", ""),
        "Сторона": side,
        "В Группе": request.form.get("subgroup", ""),
        "Категория": request.form.get("category", ""),
        "Наименование": request.form.get("product", ""),
        "Количество": request.form.get("quantity") if side != "მშრალი/Сухая" else "",
        "Оператор": request.form.get("operator", ""),
        "Комментарий": request.form.get("comment", ""),
        "gp_padoni": request.form.get("gp_padoni") or 0,
        "gp_ryadi": request.form.get("gp_ryadi") or 0,
        "brak_padoni": request.form.get("brak_padoni") or 0,
        "brak_ryadi": request.form.get("brak_ryadi") or 0,
        "uc_padoni": request.form.get("uc_padoni") or 0,
        "uc_ryadi": request.form.get("uc_ryadi") or 0,
    }

    try:
        new_entry = Result(
            zavod=data["Завод"],
            storona=data["Сторона"],
            v_gruppe=data["В Группе"],
            kategoriya=data["Категория"],
            naimenovanie=data["Наименование"],
            kolichestvo=data["Количество"],
            operator=data["Оператор"],
            comment=data["Комментарий"],
            gp_padoni=int(data["gp_padoni"]),
            gp_ryadi=int(data["gp_ryadi"]),
            brak_padoni=int(data["brak_padoni"]),
            brak_ryadi=int(data["brak_ryadi"]),
            uc_padoni=int(data["uc_padoni"]),
            uc_ryadi=int(data["uc_ryadi"])
        )
        db.session.add(new_entry)
        db.session.commit()
        app.logger.info(f"✅ Entry saved successfully: {data}")
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"❌ Error saving to database: {str(e)}", exc_info=True)
        return "❌ Error saving data.", 500

    operator = session.get("user")
    return render_template("submit.html", data=data, operator=operator)






@app.route("/restart")
def restart():
    """
    Clears the session (except for the factory) to start a new data entry process.
    """
    preserved_factory = session.get("factory")
    for key in ["side", "subgroup", "category", "product"]:
        session.pop(key, None)
    if preserved_factory:
        session["factory"] = preserved_factory
    return redirect(url_for("select_side"))





@app.route("/export_admin_csv")
def export_admin_csv():
    """
    Exports all records from the 'results' table to a CSV file. Admin only.
    """
    if session.get("user") != "admin":
        return redirect(url_for("login"))

    try:
        results = Result.query.order_by(Result.created_at.desc()).all()

        si = io.StringIO()
        cw = csv.writer(si)

        cw.writerow([
            "ID", "Количество", "Готовая продукция (Падони)", "Готовая продукция (Ряди)",
            "Брак (Падони)", "Брак (Ряди)", "Уцененная (Падони)", "Уцененная (Ряди)",
            "Наименование", "Артикул", "Группа",
            "Категория", "Сторона", "Оператор", "Дата/Время", "Комментарий", "Статус", "Причина удаления"
        ])

        for r in results:
            status = "Удалено" if r.delete_comment else "Активно"
            reason = r.delete_comment or ""
            artikul = name_to_artikul.get(r.naimenovanie, "")
            kolichestvo = r.kolichestvo if r.storona != "მშრალი/Сухая" else ""

            cw.writerow([
                r.id,
                kolichestvo,
                r.gp_padoni if r.storona == "მშრალი/Сухая" else "",
                r.gp_ryadi if r.storona == "მშრალი/Сухая" else "",
                r.brak_padoni if r.storona == "მშრალი/Сухая" else "",
                r.brak_ryadi if r.storona == "მშრალი/Сухая" else "",
                r.uc_padoni if r.storona == "მშრალი/Сухая" else "",
                r.uc_ryadi if r.storona == "მშრალი/Сухая" else "",
                r.naimenovanie or "",
                artikul,
                r.v_gruppe or "",
                r.kategoriya or "",
                r.storona or "",
                r.operator or "",
                r.created_at.strftime('%d.%m.%Y %H:%M:%S') if r.created_at else "",
                r.comment or "",
                status,
                reason
            ])

        output = make_response('\ufeff' + si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=admin_history.csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8"
        return output

    except Exception as e:
        app.logger.error("❌ Error exporting CSV:", exc_info=True)
        return f"❌ Error exporting CSV: {str(e)}", 500







@app.route("/edit_result/<int:result_id>", methods=["GET", "POST"])
def edit_result(result_id):
    """
    Allows an operator to edit their own records. Logs changes to EditHistory.
    """
    result = Result.query.get_or_404(result_id)
    operator = session.get("user", "unknown")

    if request.method == "POST":
        changes = []

        editable_fields = ["kolichestvo", "comment"]
        if result.storona == "მშრალი/Сухая":
            editable_fields += ["gp_padoni", "gp_ryadi", "brak_padoni", "brak_ryadi", "uc_padoni", "uc_ryadi"]

        for field in editable_fields:
            new_value = request.form.get(field)
            old_value = getattr(result, field)
            old_str = str(old_value) if old_value is not None else ""
            new_str = str(new_value) if new_value is not None else ""

            if new_str != old_str:
                changes.append((field, old_str, new_str))
                setattr(result, field, new_value)

        if changes:
            for field, old, new in changes:
                db.session.add(EditHistory(
                    result_id=result.id,
                    field_name=field,
                    old_value=old,
                    new_value=new,
                    edited_by=operator
                ))
            db.session.commit()
            flash("Изменения сохранены", "success")
        else:
            flash("Ничего не изменено", "info")

        return redirect(url_for("operator_history"))

    FIELD_LABELS = {
        "kolichestvo": "Количество",
        "comment": "Комментарий",
        "gp_padoni": "Готовая продукция (Падони)",
        "gp_ryadi": "Готовая продукция (Ряди)",
        "brak_padoni": "Брак (Падони)",
        "brak_ryadi": "Брак (Ряди)",
        "uc_padoni": "Уцененная (Падони)",
        "uc_ryadi": "Уцененная (Ряди)",
    }

    return render_template("edit_result.html", result=result, FIELD_LABELS=FIELD_LABELS)




@app.route("/mark_deleted/<int:result_id>", methods=["POST"])
def mark_deleted(result_id):
    """
    Soft-deletes a record by adding a deletion comment.
    """
    result = Result.query.get_or_404(result_id)

    reason = request.form.get("reason", "").strip()
    if not reason:
        reason = "Удалено без указания причины"

    result.delete_comment = reason

    try:
        db.session.commit()
        flash(f"Запись ID {result.id} помечена как удалённая.", "info")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Ошибка при пометке удаления: {str(e)}", exc_info=True)
        flash("❌ Не удалось сохранить удаление", "error")

    return redirect(url_for("operator_history"))




# === App Runner === #
if __name__ == "__main__":
    app.run(debug=True)
