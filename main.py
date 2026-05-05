from flask import Flask, render_template, redirect, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    avatar = db.Column(db.String(200))

class Place(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(200))
    coordinates = db.Column(db.String(200))
    is_favorite = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def index():
    query = Place.query

    if current_user.is_authenticated:
        query = query.filter_by(user_id=current_user.id)

        if request.args.get('favorite'):
            query = query.filter_by(is_favorite=True)

        places_db = query.all()
    else:
        places_db = []

    places = []
    for p in places_db:
        places.append({
            "id": p.id,
            "city": p.city,
            "coordinates": p.coordinates,
            "is_favorite": p.is_favorite
        })

    return render_template('index.html', places=places)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        if User.query.filter_by(username=username).first():
            flash('Пользователь уже существует')
            return redirect('/register')

        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна')
        return redirect('/login')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()

        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect('/')
        else:
            flash('Неверные данные')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


@app.route('/search', methods=['POST'])
@login_required
def search():
    city = request.form.get('city')

    if not city:
        flash("Введите город")
        return redirect('/')

    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": city, "format": "json"}
        headers = {"User-Agent": "flask-app"}

        response = requests.get(url, params=params, headers=headers)
        data = response.json()

        if not data:
            flash("Город не найден")
            return redirect('/')

        lat = data[0]['lat']
        lon = data[0]['lon']

        coordinates = f"{lon} {lat}"

        place = Place(city=city, coordinates=coordinates, user_id=current_user.id)
        db.session.add(place)
        db.session.commit()

        flash(f"Найдено: {lat}, {lon}")

    except Exception as e:
        print("ERROR:", e)
        flash("Ошибка поиска")

    return redirect('/')


@app.route('/favorite/<int:id>')
@login_required
def favorite(id):
    place = Place.query.get(id)

    if place and place.user_id == current_user.id:
        place.is_favorite = not place.is_favorite
        db.session.commit()

    return redirect('/')


@app.route('/delete/<int:id>')
@login_required
def delete(id):
    place = Place.query.get(id)

    if place and place.user_id == current_user.id:
        db.session.delete(place)
        db.session.commit()

    return redirect('/')


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')


@app.route('/update_username', methods=['POST'])
@login_required
def update_username():
    new_username = request.form.get('username')

    if not new_username:
        flash("Введите имя")
        return redirect('/profile')

    if User.query.filter_by(username=new_username).first():
        flash("Имя уже занято")
        return redirect('/profile')

    user = User.query.get(current_user.id)
    user.username = new_username
    db.session.commit()

    flash("Имя обновлено")
    return redirect('/profile')


@app.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files['file']

    if file:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(path)

        user = User.query.get(current_user.id)
        user.avatar = path
        db.session.commit()

    return redirect('/profile')


with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True)