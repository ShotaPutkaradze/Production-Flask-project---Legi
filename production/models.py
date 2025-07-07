from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Result(db.Model):
    __tablename__ = 'results'

    id = db.Column(db.Integer, primary_key=True)
    zavod = db.Column(db.String(100))
    storona = db.Column(db.String(100))
    v_gruppe = db.Column(db.String(100))
    kategoriya = db.Column(db.String(100))
    naimenovanie = db.Column(db.String(200))
    kolichestvo = db.Column(db.String(50))
    operator = db.Column(db.String(100))

    # ✅ NEW FIELDS
    gp_padoni = db.Column(db.Integer)
    gp_ryadi = db.Column(db.Integer)
    brak_padoni = db.Column(db.Integer)
    brak_ryadi = db.Column(db.Integer)
    
    # --- დამატებული ველები ---
    uc_padoni = db.Column(db.Integer)
    uc_ryadi = db.Column(db.Integer)
    # --- დასასრული ---

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    comment = db.Column(db.Text)
    delete_comment = db.Column(db.Text)


class EditHistory(db.Model):
    __tablename__ = 'edit_history'

    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey('results.id'), nullable=False)
    field_name = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    edited_by = db.Column(db.String(100))  # operator/admin username
    edited_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    result = db.relationship('Result', backref='edit_logs')
