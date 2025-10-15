from flask import Flask, render_template, request, redirect, send_file, session, flash, url_for, flash
from models import db, User, Player, Test, TestSession, TestResult
import pandas as pd
import os
import statistics
from functools import wraps
app = Flask(__name__)
app.debug = True
import random
import string
import csv
from io import StringIO
from flask import Response
# adding configuration for using a sqlite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jacfit.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'supersecret'

# Creating an SQLAlchemy instance
db.init_app(app)

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def coach_only(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "coach":
            flash("Access denied: Coach only.")
            return redirect(url_for("dashboard.html"))
        return f(*args, **kwargs)
    return wrapper

@app.route('/dashboard')
@login_required
@coach_only
def dashboard():
    return render_template("dashboard.html")

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return redirect(url_for("register"))
        user = User(email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Registration successful! Please log in.")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route('/login', methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session["user_id"] = user.user_id
            session["role"] = user.role
            flash("Login successful.")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials")
    return render_template("login.html")
        
# ROUTES
@app.route('/')
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    players = Player.query.all()
    tests = Test.query.all()
    return render_template('index.html', players=players, tests=tests)

# ---- PLAYER ROUTES ----
@app.route('/dashboard/players')
@login_required
@coach_only
def players_page():
    players = Player.query.all()
    return render_template('players.html', players=players)

@app.route('/add_player', methods=["POST"])
def add_player():
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    age = request.form.get("age")

    if first_name and last_name and age:
        p = Player(first_name=first_name, last_name=last_name, age=int(age))
        db.session.add(p)
        db.session.commit()
    return redirect('/dashboard/players')

@app.route('/delete_player/<int:id>')
@login_required
@coach_only
def delete_player(id): 
    player = Player.query.get(id)
    if player:
        db.session.delete(player)
        db.session.commit()
    return redirect('/dashboard/players')

@app.route('/edit_player/<int:player_id>', methods=["GET", "POST"])
@login_required
@coach_only
def edit_player(player_id):
    player = Player.query.get_or_404(player_id)

    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        age = request.form.get("age")

        if first_name and last_name and age:
            player.first_name = first_name
            player.last_name = last_name
            player.age = int(age)
            db.session.commit()
            return redirect(url_for('players_page'))

    return render_template("edit_player.html", player=player)

def generate_accounts():
    if request.method == "POST":
        players = Player.query.all()
        account_data = []

        for player in players:
            # Check if account already exists
            user = User.query.filter_by(player_id=player.player_id).first()
            if not user:
                temp_password = generate_temp_password()
                username = f"{player.first_name.lower()}.{player.last_name.lower()}"
                
                user = User(
                    email=username + "@example.com",  # Use email as login
                    role="player",
                    player_id=player.player_id
                )
                user.set_password(temp_password)  # Hash and store
                user.temp_password = temp_password  # Save for CSV export
                db.session.add(user)
                
                account_data.append({
                    "Player ID": player.player_id,
                    "First Name": player.first_name,
                    "Last Name": player.last_name,
                    "Username": username,
                    "Temp Password": temp_password
                })

        db.session.commit()

        # Generate CSV for download
        if account_data:
            si = StringIO()
            writer = csv.DictWriter(si, fieldnames=["Player ID","First Name","Last Name","Username","Temp Password"])
            writer.writeheader()
            writer.writerows(account_data)
            output = si.getvalue()
            return Response(
                output,
                mimetype="text/csv",
                headers={"Content-Disposition":"attachment;filename=player_accounts.csv"}
            )
        else:
            flash("All players already have accounts.")
            return redirect(url_for("dashboard"))

    return render_template("generate_accounts.html")

# Player profile routes
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

@app.route('/edit_result/<int:score_id>', methods=["GET", "POST"])
@login_required
@coach_only
def edit_result(score_id):
    result = TestResult.query.get_or_404(score_id)

    if request.method == "POST":
        new_score = request.form.get("score")
        if new_score:
            result.score = float(new_score)
            db.session.commit()
            return redirect(url_for('player_profile', player_id=result.player_id))

    return render_template("edit_result.html", result=result)

# ---- TEST ROUTES ----
@app.route('/dashboard/tests')
@login_required
@coach_only
def tests_page():
    tests = Test.query.all()
    return render_template('tests.html', tests=tests)

@app.route('/add_test', methods=["POST"])
def add_test():
    test_name = request.form.get("test_name")
    description = request.form.get("Description")
    unit = request.form.get("unit")
    better_score = request.form.get("better_score") #high or low

    if test_name and better_score:
        t = Test(test_name=test_name, 
                 description=description, 
                 unit=unit, 
                 better_score=better_score
                 )
        db.session.add(t)
        db.session.commit()
    return redirect('/dashboard/tests')

@app.route('/delete_test/<int:id>')
def delete_test(id):
    test = Test.query.get(id)
    if test:
        db.session.delete(test)
        db.session.commit()
    return redirect('/dashboard/tests')

@app.route('/edit_test/<int:test_id>', methods=["GET", "POST"])
@login_required
@coach_only
def edit_test(test_id):
    test = Test.query.get_or_404(test_id)

    if request.method == "POST":
        test_name = request.form.get("test_name")
        description = request.form.get("description")
        unit = request.form.get("unit")
        better_score = request.form.get("better_score")  # 'high' or 'low'

        if test_name and better_score:
            test.test_name = test_name
            test.description = description
            test.unit = unit
            test.better_score = better_score
            db.session.commit()
            return redirect(url_for('tests_page'))  # assuming you have a tests_page route

    return render_template("edit_test.html", test=test)

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
            return redirect(url_for('dashboard'))

    return render_template('upload.html')

#Results routes

@app.route('/dashboard/results')
@login_required
@coach_only
def results_page():
    sessions = TestSession.query.order_by(TestSession.year.desc(), TestSession.month.desc()).all()
    tests = Test.query.all()

    selected_session_id = request.args.get('session_id', type=int)
    selected_test_id = request.args.get('test_id', type=int)
    sort_by = request.args.get('sort_by', default='score')
    order = request.args.get('order', default='desc')

    filtered_results = []
    selected_session = None
    selected_test = None

    if selected_session_id and selected_test_id:
        selected_session = TestSession.query.get(selected_session_id)
        selected_test = Test.query.get(selected_test_id)

        query = (
            TestResult.query
            .join(Player)
            .filter(
                TestResult.session_id == selected_session_id,
                TestResult.test_id == selected_test_id
            )
        )

        #Sorting logic
        if sort_by == 'first_name':
            query = query.order_by(Player.first_name.asc() if order == 'asc' else Player.first_name.desc())
        elif sort_by == 'last_name':
            query = query.order_by(Player.last_name.asc() if order == 'asc' else Player.last_name.desc())
        elif sort_by == 'player_id':
            query = query.order_by(Player.player_id.asc() if order == 'asc' else Player.player_id.desc())
        elif sort_by == 'rank':
            if selected_test.better_score == 'high':
                query = query.order_by(TestResult.score.desc() if order == 'desc' else TestResult.score.asc())
            else:
                query = query.order_by(TestResult.score.asc() if order == 'desc' else TestResult.score.desc())
        elif sort_by ==  'score':
            query = query.order_by(TestResult.score.asc() if order == 'asc' else TestResult.score.desc())


        filtered_results = query.all()

        if selected_test.better_score == 'high':
            sorted_for_rank = sorted(filtered_results, key=lambda r: r.score if r.score is not None else -float('inf'), reverse=True)
        else:
            sorted_for_rank = sorted(filtered_results, key=lambda r: r.score if r.score is not None else float('inf'))

        rank_map = {result.score_id: idx + 1 for idx, result in enumerate(sorted_for_rank)}

        for result in filtered_results:
            result.rank = rank_map[result.score_id]

    return render_template(
        'results.html',
        sessions=sessions,
        tests=tests,
        selected_session=selected_session,
        selected_test=selected_test,
        filtered_results=filtered_results,
        sort_by=sort_by,
        order=order,
    )


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email="emmapiers4@gmail.com").first():
            user = User(email="emmapiers4@gmail.com", role="coach")
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            print("Test coach account created")
    app.run(debug=True)