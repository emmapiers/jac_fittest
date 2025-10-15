from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Create the SQLAlchemy db object here
db = SQLAlchemy()

class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    player_profile = db.relationship("Player", backref="user", uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
class Player(db.Model):
    player_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(20), nullable=False)
    last_name = db.Column(db.String(20), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'))

    def __repr__(self):
        return f"Name : {self.first_name}, Age: {self.age}"

class Test(db.Model):
    test_id = db.Column(db.Integer, primary_key=True)
    test_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    unit = db.Column(db.String(20), nullable=True)
    better_score = db.Column(db.String(10), nullable=False)

    def __repr__(self):
        return f"Test: {self.test_name}, Unit: {self.unit}"

class TestSession(db.Model):
    session_id = db.Column(db.Integer, primary_key = True)
    month = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f"Session: {self.month} {self.year}"
    
class TestResult(db.Model):
    score_id = db.Column(db.Integer, primary_key = True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.player_id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.test_id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('test_session.session_id'), nullable=False)
    score = db.Column(db.Float, nullable=True)

    player = db.relationship('Player', backref='scores')
    test = db.relationship('Test', backref='scores')
    session = db.relationship('TestSession', backref='results')

    def __repr__(self):
        return f"<TestResult player_id={self.player_id}, test_id={self.test_id}, session={self.session_id}, score={self.score}>"
