# app.py
from flask import Flask, render_template, request, make_response, session, url_for, flash, redirect
from models import db, Result, EditHistory
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







# === Flask App Setup === #
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:0okmNJI(!@localhost/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
app.secret_key = secrets.token_hex(16)

# === Logging === #
os.makedirs('logs', exist_ok=True)
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
file_handler.setLevel(logging.INFO) 
app.logger.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
app.logger.addHandler(file_handler)


with app.app_context():
    db.create_all()

    # Load operators.csv
    operators_df = pd.read_csv('operators.csv', encoding='utf-8-sig')
    credentials = {}
    for _, row in operators_df.iterrows():
        credentials[row["username"]] = {
            "password": str(row["password"]), # Ensure password is a string
            "Завод": row["Завод"]
        }
    operator_factories = dict(zip(operators_df['username'], operators_df['Завод']))


# === CSV Data === #
try:
    # Explicitly set encoding to handle potential BOM and UTF-8 issues
    df = pd.read_csv("nomenclature.csv", encoding='utf-8-sig')
    app.logger.info("✅ nomenclature.csv loaded successfully.")
except FileNotFoundError:
    df = pd.DataFrame()
    app.logger.error("❌ FATAL: nomenclature.csv not found. The application cannot function.")




# === Utility Function === #
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def get_unique(column, **filters):
    filtered_df = df.copy()
    
    # Strip whitespace from all object columns to prevent matching issues
    for col in filtered_df.select_dtypes(['object']):
        if pd.api.types.is_string_dtype(filtered_df[col]):
             filtered_df[col] = filtered_df[col].str.strip()

    for col, val in filters.items():
        if val:
            stripped_val = val.strip()
            filtered_df = filtered_df[filtered_df[col] == stripped_val]
            
    unique_list = filtered_df[column].dropna().unique()
    result = sorted(unique_list, key=natural_sort_key)

    return result

# === Routes === #
@app.route("/", methods=["GET", "POST"])
def login():
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
    session.clear()
    return redirect(url_for("login"))


@app.route("/report")
def report():
    if "user" not in session:
        return redirect(url_for("login"))
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    selected_operator = request.args.get('operator')
    
    totals = None
    results = []

    # Fetch all operators for the dropdown
    all_operators = [op[0] for op in db.session.query(Result.operator).distinct().order_by(Result.operator).all()]

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            
            query = Result.query.filter(
                Result.created_at >= start_date,
                Result.created_at < end_date
            )

            if selected_operator:
                query = query.filter(Result.operator == selected_operator)
            
            results = query.order_by(Result.created_at.desc()).all()

            # --- Python-side summation for robustness ---
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
                    pass 

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
            # --- End of Python-side summation ---

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
    if session.get("user") != "admin":
        return redirect(url_for("login"))

    try:
        page = request.args.get("page", 1, type=int)
        per_page = 100

        pagination = Result.query.order_by(Result.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        results = pagination.items

        name_to_artikul = dict(zip(df["Наименование"], df["Артикул"]))
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
        app.logger.error("Ошибка при получении истории (admin):", exc_info=True)
        return f"❌ Ошибка при получении истории: {str(e)}", 500



@app.route("/operator_history")
def operator_history():
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

        name_to_artikul = dict(zip(df["Наименование"], df["Артикул"]))
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
        app.logger.error("Ошибка при получении истории оператора:", exc_info=True)
        return f"❌ Ошибка при получении истории оператора: {str(e)}", 500



@app.route("/side", methods=["GET", "POST"])
def select_side():
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
    sides = get_unique("Сторона", Завод=factory)

    full_history = Result.query.filter_by(operator=operator).order_by(Result.created_at.desc()).all()

    return render_template(
        "side.html",
        factory=factory,
        sides=sides,
        operator=operator,
        results=full_history
    )



@app.route("/subgroup", methods=["GET", "POST"])
def select_subgroup():
    if request.method == "POST":
        factory = request.form.get("factory", "").strip()
        side = request.form.get("side", "").strip()

        session["factory"] = factory
        session["side"] = side
    else:
        factory = session.get("factory")
        side = session.get("side")
        if not all([factory, side]):
            return redirect(url_for("select_side"))

    subgroup = request.form.get("subgroup")
    if subgroup:
        session["subgroup"] = subgroup
        return redirect(url_for("select_category"))
        
    subgroups = get_unique("В Группе", Завод=factory, Сторона=side)
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
    if request.method == "POST":
        factory = request.form.get("factory", "").strip()
        side = request.form.get("side", "").strip()
        subgroup = request.form.get("subgroup", "").strip()

        session["factory"] = factory
        session["side"] = side
        session["subgroup"] = subgroup
    else:
        factory = session.get("factory")
        side = session.get("side")
        subgroup = session.get("subgroup")

        if not all([factory, side, subgroup]):
            return redirect(url_for("select_subgroup"))

    categories = get_unique("Категория", Завод=factory, Сторона=side, **{"В Группе": subgroup})
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
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        factory = request.form.get("factory", "").strip()
        side = request.form.get("side", "").strip()
        subgroup = request.form.get("subgroup", "").strip()
        category = request.form.get("category", "").strip()

        if not category:
            return "❌ Ошибка: категория не выбрана или не передана.", 400

        session["factory"] = factory
        session["side"] = side
        session["subgroup"] = subgroup
        session["category"] = category

    else:
        factory = session.get("factory")
        side = session.get("side")
        subgroup = session.get("subgroup")
        category = session.get("category")

        if not all([factory, side, subgroup, category]):
            return redirect(url_for("select_category"))

    filtered_df = df[
        (df["Завод"] == factory) &
        (df["Сторона"] == side) &
        (df["В Группе"] == subgroup) &
        (df["Категория"] == category)
    ]
    products = get_unique("Наименование", Завод=factory, Сторона=side, **{"В Группе": subgroup, "Категория": category})

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
        app.logger.info(f"✅ Смена успешно сохранена: {data}")
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"❌ Ошибка при сохранении в базу данных: {str(e)}", exc_info=True)
        return "❌ Ошибка при сохранении данных.", 500

    operator = session.get("user")
    return render_template("submit.html", data=data, operator=operator)






@app.route("/restart")
def restart():
    preserved_factory = session.get("factory")
    for key in ["factory", "side", "subgroup", "category", "product"]:
        session.pop(key, None)
    if preserved_factory:
        session["factory"] = preserved_factory
    return redirect(url_for("select_side"))





@app.route("/export_admin_csv")
def export_admin_csv():
    if session.get("user") != "admin":
        return redirect(url_for("login"))

    try:
        results = Result.query.order_by(Result.created_at.desc()).all()

        name_to_artikul = dict(zip(df["Наименование"], df["Артикул"]))

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
        app.logger.error("❌ Ошибка при экспорте CSV:", exc_info=True)
        return f"❌ Ошибка при экспорте CSV: {str(e)}", 500







@app.route("/edit_result/<int:result_id>", methods=["GET", "POST"])
def edit_result(result_id):
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
