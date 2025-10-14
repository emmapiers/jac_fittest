from flask import Flask, render_template, request, redirect, send_file, flash, url_for
from models import db, Player, Test, TestSession, TestResult
import pandas as pd
import os
import statistics
app = Flask(__name__)
app.debug = True

# adding configuration for using a sqlite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jacfit.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'supersecret'

# Creating an SQLAlchemy instance
db.init_app(app)


# ROUTES
@app.route('/')
def index():
    players = Player.query.all()
    tests = Test.query.all()
    return render_template('index.html', players=players, tests=tests)

# ---- PLAYER ROUTES ----
@app.route('/add_player')
def add_player_page():
    return render_template('add_player.html')

@app.route('/add_player', methods=["POST"])
def add_player():
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    age = request.form.get("age")

    if first_name and last_name and age:
        p = Player(first_name=first_name, last_name=last_name, age=int(age))
        db.session.add(p)
        db.session.commit()
    return redirect('/')

@app.route('/delete_player/<int:id>')
def delete_player(id): 
    player = Player.query.get(id)
    if player:
        db.session.delete(player)
        db.session.commit()
    return redirect('/')

# ---- TEST ROUTES ----
@app.route('/add_test')
def add_test_page():
    return render_template('add_test.html')

@app.route('/add_test', methods=["POST"])
def add_test():
    test_name = request.form.get("test_name")
    description = request.form.get("description")
    unit = request.form.get("unit")

    if test_name and description and unit:
        t = Test(test_name=test_name, description=description, unit=unit)
        db.session.add(t)
        db.session.commit()
    return redirect('/')

@app.route('/delete_test/<int:id>')
def delete_test(id):
    test = Test.query.get(id)
    if test:
        db.session.delete(test)
        db.session.commit()
    return redirect('/')

# ---- DOWNLOAD ----
@app.route('/download_template')
def download_template():
    with app.app_context():
        players = Player.query.all()
        tests = Test.query.all()

        data = []
        for player in players:
            row = {
                "Player ID": player.player_id,
                "First Name": player.first_name,
                "Last Name": player.last_name
            }
            for test in tests:
                row[test.test_name] = ""
            data.append(row)

        df = pd.DataFrame(data)
        columns = ["Player ID", "First Name", "Last Name"] + [t.test_name for t in tests]
        df = df[columns]

        # Save Excel temporarily
        file_path = os.path.join(os.path.dirname(__file__), "jacfit_template.xlsx")
        df.to_excel(file_path, index=False)

        # Return it to the browser
        return send_file(file_path, as_attachment=True)
    
#--- UPLOAD --- 

@app.route('/upload', methods=['GET', 'POST'])
def upload_excel():
    if request.method == 'POST':
        month = request.form.get('month')
        year = request.form.get('year')

        if not month or not year:
            flash('Please enter a testing month and year.')
            return redirect(request.url)

        # Check if session already exists, otherwise create one
        session = TestSession.query.filter_by(month=month, year=int(year)).first()
        if not session:
            session = TestSession(month=month, year=int(year))
            db.session.add(session)
            db.session.commit()

        # --- file upload and reading ---
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)

        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(filepath)

            df = pd.read_excel(filepath)
            tests = {t.test_name: t for t in Test.query.all()}
            players = {p.player_id: p for p in Player.query.all()}

            for _, row in df.iterrows():
                player_id = row.get('Player ID')
                if pd.isna(player_id) or int(player_id) not in players:
                    continue
                player = players[int(player_id)]

                for test_name, test in tests.items():
                    if test_name not in row:
                        continue
                    score = row[test_name]
                    if pd.isna(score):
                        continue

                    existing_score = TestResult.query.filter_by(
                        player_id=player.player_id,
                        test_id=test.test_id,
                        session_id=session.session_id
                    ).first()

                    if existing_score:
                        existing_score.score = score
                    else:
                        new_score = TestResult(
                            player_id=player.player_id,
                            test_id=test.test_id,
                            session_id=session.session_id,
                            score=score
                        )
                        db.session.add(new_score)

            db.session.commit()
            flash(f"Scores uploaded for {month} {year} session!")
            return redirect(url_for('index'))

    return render_template('upload.html')

@app.route('/player/<int:player_id>')
def player_profile(player_id):
    player = Player.query.get_or_404(player_id)

    # Get all sessions the player has results in
    sessions = (
        db.session.query(TestSession)
        .join(TestResult)
        .filter(TestResult.player_id == player_id)
        .all()
    )

    session_data = {}   # Player results grouped by session
    session_stats = {}  # Best/worst/avg per test, per session

    for session in sessions:
        # Player's results in this session
        results = (
            TestResult.query
            .join(Test)
            .filter(TestResult.player_id == player_id, TestResult.session_id == session.session_id)
            .add_entity(Test)
            .all()
        )
        session_data[session] = results

        # Calculate session-wide stats per test
        stats_per_test = {}
        for r, t in results:
            # All players' results for this same test and session
            test_scores = [
                tr.score
                for tr in TestResult.query.filter(
                    TestResult.session_id == session.session_id,
                    TestResult.test_id == t.test_id
                ).all()
                if tr.score is not None
            ]

            if test_scores:
                stats_per_test[t.test_id] = {
                    "best": max(test_scores),
                    "worst": min(test_scores),
                    "avg": sum(test_scores) / len(test_scores)
                }
            else:
                stats_per_test[t.test_id] = {"best": 0, "worst": 0, "avg": 0}

        session_stats[session] = stats_per_test

    return render_template(
        'player_profile.html',
        player=player,
        session_data=session_data,
        session_stats=session_stats
    )

@app.route('/players')
def show_players():
    players = Player.query.all()
    return render_template('players.html', players=players)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)