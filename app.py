
import csv
from io import TextIOWrapper
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy import func, extract
from werkzeug.security import generate_password_hash, check_password_hash
from flask_restful import Api, Resource
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from dotenv import load_dotenv
import os


load_dotenv()


app = Flask(__name__)
app.secret_key = "supersecretkey"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expense.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = "jwt-secret-key"

db = SQLAlchemy(app)
api = Api(app)
jwt = JWTManager(app)


from transformers import pipeline

classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli"
)

INTENT_LABELS = [
    "TOTAL_EXPENSE",
    "CATEGORY_EXPENSE",
    "MONTHLY_SUMMARY",
    "SAVING_ADVICE",
    "GENERAL_CHAT"
]

def get_intent_llm(message):
    result = classifier(message, INTENT_LABELS)
    return result["labels"][0]


class User_Model(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(200), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)


class Expense_Model(db.Model):
    __tablename__ = "expenses"
    id = db.Column(db.Integer, primary_key=True)
    Amt = db.Column(db.Integer, nullable=False)
    Type = db.Column(db.String(200), nullable=False)
    Desc = db.Column(db.String(200), nullable=False)
    date_time = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


with app.app_context():
    db.create_all()


def total_expense_this_month(user_id):
    now = datetime.now()
    return db.session.query(func.sum(Expense_Model.Amt)).filter(
        Expense_Model.user_id == user_id,
        extract("month", Expense_Model.date_time) == now.month,
        extract("year", Expense_Model.date_time) == now.year
    ).scalar() or 0


def category_expense_this_month(user_id, category):
    now = datetime.now()
    return db.session.query(func.sum(Expense_Model.Amt)).filter(
        Expense_Model.user_id == user_id,
        Expense_Model.Type.ilike(f"%{category}%"),
        extract("month", Expense_Model.date_time) == now.month,
        extract("year", Expense_Model.date_time) == now.year
    ).scalar() or 0

@app.route("/chat", methods=["POST"])
def chat():
    if "user_id" not in session:
        return jsonify({"reply": "Please login first"}), 401

    data = request.get_json()
    message = data.get("message", "")
    user_id = session["user_id"]

    intent = get_intent_llm(message)

    session["last_intent"] = intent
    session["last_message"] = message.lower()

    if intent == "TOTAL_EXPENSE":
        total = total_expense_this_month(user_id)
        reply = f"Your total expense this month is ₹{total} 💸"

    elif intent == "CATEGORY_EXPENSE":
        categories = ["food", "travel", "shopping", "bills", "entertainment", "groceries"]
        msg = message.lower()

        category = next((c for c in categories if c in msg), None)

        if not category:
            reply = "Please mention a category like food, travel, shopping, etc."
        else:
            amount = category_expense_this_month(user_id, category)
            reply = f"You spent ₹{amount} on {category} this month 🍽️"

    elif intent == "SAVING_ADVICE":
        reply = "You could save money by reducing impulse purchases and tracking subscriptions 🧠"

    else:
        reply = "I can help you analyze your expenses 😊"

    return jsonify({"reply": reply})

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User_Model.query.filter_by(username=request.form["username"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            session["user_id"] = user.id
            return redirect(url_for("dashboard"))
        flash("Invalid credentials")
    return render_template("login.html")

@app.route("/upload_upi", methods=["POST"])
def upload_upi():
    if "user_id" not in session:
        return redirect(url_for("login"))


    file=request.files["upi_file"]

    if not file.filename.endswith(".csv"):
        flash("Please upload a CSV file")
        return redirect(url_for("dashboard"))

    csv_file = TextIOWrapper(file, encoding="utf-8")
    reader = csv.DictReader(csv_file)

    for row in reader:
        expense = Expense_Model(
            Amt=int(float(row["Amount"])),
            Type=row.get("Category", "Other"),
            Desc=row.get("Description", "UPI Transaction"),
            date_time=datetime.strptime(row["Date"], "%Y-%m-%d"),
            user_id=session["user_id"]
        )
        db.session.add(expense)

    db.session.commit()
    flash("UPI transactions imported successfully!")
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if User_Model.query.filter_by(username=request.form["username"]).first():
            flash("User already exists")
            return redirect(url_for("register"))

        user = User_Model(username=request.form["username"])
        user.set_password(request.form["password"])
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        expense = Expense_Model(
            Amt=int(request.form["Amt"]),
            Type=request.form["Type"],
            Desc=request.form["Desc"],
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


if __name__ == "__main__":
    app.run(port=5001, debug=True)

