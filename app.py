from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from flask_restful import Api, Resource
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)


app = Flask(__name__)

app.secret_key = "supersecretkey"
app.config["JWT_SECRET_KEY"] = "jwt-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expense.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
api = Api(app)
jwt = JWTManager(app)

# -------------------- HELPERS --------------------
def expense_to_dict(expense):
    return {
        "id": expense.id,
        "amount": expense.Amt,
        "type": expense.Type,
        "description": expense.Desc,
        "date_time": expense.date_time.isoformat()
    }

# -------------------- MODELS --------------------
class User_Model(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(200), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def __repr__(self):
        return f"User {self.username}"


class Expense_Model(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    Amt = db.Column(db.Integer, nullable=False)
    Type = db.Column(db.String(200), nullable=False)
    Desc = db.Column(db.String(200), nullable=False)
    date_time = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    def __repr__(self):
        return f"Expense {self.id} - {self.Type}"

# -------------------- WEB ROUTES (HTML) --------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User_Model.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if User_Model.query.filter_by(username=username).first():
            flash("User already exists")
            return redirect(url_for("register"))

        user = User_Model(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        Amt = int(request.form["Amt"])
        Type = request.form["Type"]
        Desc = request.form["Desc"]

        expense = Expense_Model(
            Amt=Amt,
            Type=Type,
            Desc=Desc,
            user_id=session["user_id"]
        )
        db.session.add(expense)
        db.session.commit()
        return redirect(url_for("dashboard"))

    user_id = session["user_id"]
    expenses = Expense_Model.query.filter_by(user_id=user_id).all()
    today = date.today()

    total_today = db.session.query(func.sum(Expense_Model.Amt))\
        .filter(Expense_Model.user_id == user_id,
                func.date(Expense_Model.date_time) == today)\
        .scalar() or 0

    total_month = db.session.query(func.sum(Expense_Model.Amt))\
        .filter(Expense_Model.user_id == user_id,
                func.strftime('%Y-%m', Expense_Model.date_time) == today.strftime('%Y-%m'))\
        .scalar() or 0

    return render_template(
        "index.html",
        allExpense=expenses,
        total_today=total_today,
        total_month=total_month
    )


@app.route("/update/<int:id>", methods=["GET", "POST"])
def update(id):
    expense = Expense_Model.query.filter_by(id=id).first_or_404()

    if request.method == "POST":
        expense.Amt = int(request.form["Amt"])
        expense.Type = request.form["Type"]
        expense.Desc = request.form["Desc"]
        db.session.commit()
        return redirect(url_for("dashboard"))

    return render_template("update.html", expense=expense)


@app.route("/delete/<int:id>")
def delete(id):
    expense = Expense_Model.query.filter_by(id=id).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))


class ApiLogin(Resource):
    def post(self):
        data = request.get_json()
        user = User_Model.query.filter_by(username=data["username"]).first()

        if user and check_password_hash(user.password, data["password"]):
            token = create_access_token(identity=user.id)
            return {"access_token": token}, 200

        return {"message": "Invalid credentials"}, 401


class ExpenseListAPI(Resource):

    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        expenses = Expense_Model.query.filter_by(user_id=user_id).all()
        return [expense_to_dict(e) for e in expenses], 200

    @jwt_required()
    def post(self):
        user_id = get_jwt_identity()
        data = request.get_json()

        expense = Expense_Model(
            Amt=data["amount"],
            Type=data["type"],
            Desc=data["description"],
            user_id=user_id
        )
        db.session.add(expense)
        db.session.commit()

        return expense_to_dict(expense), 201


class ExpenseAPI(Resource):

    @jwt_required()
    def put(self, id):
        user_id = get_jwt_identity()
        expense = Expense_Model.query.filter_by(id=id, user_id=user_id).first_or_404()

        data = request.get_json()
        expense.Amt = data["amount"]
        expense.Type = data["type"]
        expense.Desc = data["description"]

        db.session.commit()
        return expense_to_dict(expense), 200

    @jwt_required()
    def delete(self, id):
        user_id = get_jwt_identity()
        expense = Expense_Model.query.filter_by(id=id, user_id=user_id).first_or_404()
        db.session.delete(expense)
        db.session.commit()
        return {"message": "Deleted"}, 200


api.add_resource(ApiLogin, "/api/login")
api.add_resource(ExpenseListAPI, "/api/expenses")
api.add_resource(ExpenseAPI, "/api/expenses/<int:id>")


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


