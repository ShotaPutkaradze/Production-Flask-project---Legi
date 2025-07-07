# models.py
from app import db

# These models now use the original attribute names (zavod, storona, etc.)
# and constraints (unique=True on 'artikul') to perfectly match your
# existing database schema.

class Nomenclature(db.Model):
    __tablename__ = 'nomenclature'
    id = db.Column(db.Integer, primary_key=True)
    zavod = db.Column(db.String(100), nullable=False)
    storona = db.Column(db.String(100), nullable=False)
    v_gruppe = db.Column(db.String(100), nullable=False)
    kategoriya = db.Column(db.String(200), nullable=False)
    naimenovanie = db.Column(db.String(200), nullable=False)
    # CORRECTED: The unique constraint is on 'artikul', not 'naimenovanie'.
    artikul = db.Column(db.String(100), nullable=False, unique=True)

    def __repr__(self):
        return f'<Nomenclature {self.naimenovanie}>'

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
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    delete_comment = db.Column(db.Text)
    gp_padoni = db.Column(db.Integer)
    gp_ryadi = db.Column(db.Integer)
    brak_padoni = db.Column(db.Integer)
    brak_ryadi = db.Column(db.Integer)
    uc_padoni = db.Column(db.Integer)
    uc_ryadi = db.Column(db.Integer)

    def __repr__(self):
        return f'<Result {self.id} - {self.naimenovanie}>'

class EditHistory(db.Model):
    __tablename__ = 'edit_history'
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey('results.id'), nullable=False)
    field_name = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    edited_by = db.Column(db.String(100))
    edited_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    result = db.relationship('Result', backref=db.backref('edit_logs', lazy=True))

    def __repr__(self):
        return f'<EditHistory for Result ID {self.result_id}>'
