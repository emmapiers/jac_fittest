from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import pandas as pd

# --- configure app ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jacfit.db'  # same file as your Flask app
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- define models (or import from models.py) ---
class Player(db.Model):
    player_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(20), nullable=False)
    last_name = db.Column(db.String(20), nullable=False)
    age = db.Column(db.Integer, nullable=False)

class Test(db.Model):
    test_id = db.Column(db.Integer, primary_key=True)
    test_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    unit = db.Column(db.String(20), nullable=False)

# --- query database and generate Excel ---
with app.app_context():
    players = Player.query.all()
    tests = Test.query.all()

    data = []
    for player in players:
        row = {"Player ID": player.player_id,
               "First Name": player.first_name,
               "Last Name": player.last_name}
        for test in tests:
            row[test.test_name] = ""
        data.append(row)

    df = pd.DataFrame(data)
    columns = ["Player ID", "First Name", "Last Name"] + [t.test_name for t in tests]
    df = df[columns]

    df.to_excel("jacfit_template.xlsx", index=False)
    print("Excel generated: jacfit_template.xlsx")
