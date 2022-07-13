import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    transactions_db = db.execute(
        "SELECT symbol, name, SUM(shares) AS shares, price, SUM(total) AS total FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
    cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = cash_db[0]["cash"]
    return render_template("index.html", database=transactions_db, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    # Buy shares of stock
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("THIS IS NOT A NUMBER")
        if not symbol:
            return apology("Must give a symbol")

        stock = lookup(symbol.upper())
        if stock == None:
            return apology("Symbol does not exist")
        if shares < 0:
            return apology("Shares are not allowed")

        transistion_value = shares * stock["price"]
        user_id = session["user_id"]
        user_cash_db = db.execute("select cash from users where id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]

        if transistion_value > user_cash:
            return apology("You don't have enough money")
        updt_user_cash = user_cash - transistion_value
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updt_user_cash, user_id)
        date = datetime.datetime.now()
        db.execute("INSERT INTO transactions (user_id, symbol, name, shares, price, total, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   user_id, stock["symbol"], stock["name"], shares, stock["price"], transistion_value, date)
        flash("Bought!")
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions_db = db.execute("SELECT symbol, shares, price, date FROM transactions WHERE user_id = ?", user_id)
    return render_template("history.html", transactions=transactions_db)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Must give a symbol")

        stock = lookup(symbol.upper())
        if stock == None:
            return apology("Symbol does not exist")
        return render_template("quoted.html", name=stock["name"], price=stock["price"], symbol=stock["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        # Check requirements are not empty
        if not username:
            return apology("Missing Username")
        if not password:
            return apology("Missing Password")
        if not confirmation:
            return apology("Missing Confirmation")
        # check pass
        if password != confirmation:
            return apology("Passwords do not match!")
        # Hash pass and add it to the db
        hash = generate_password_hash(password)
        try:
            new_user = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
        except:
            return apology("Username is already exists")

        # Remember which user has registerd
        session["user_id"] = new_user
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        user_id = session["user_id"]
        symbols_db = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", user_id)
        return render_template("sell.html", symbols=symbols_db)
    else:
        user_id = session["user_id"]
        symbol = request.form.get("symbol")
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("THIS IS NOT A NUMBER")
        if not symbol:
            return apology("Must give a symbol")

        stock = lookup(symbol.upper())
        if stock == None:
            return apology("Symbol does not exist")
        if shares <= 0:
            return apology("Shares are not allowed")

        transistion_value = shares * stock["price"]
        user_cash_db = db.execute("select cash from users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]

        user_shares_db = db.execute(
            "select shares from transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, symbol)
        user_shares = user_shares_db[0]["shares"]

        if shares > user_shares:
            return apology("TOO MANY SHARES")

        updt_user_cash = user_cash + transistion_value
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updt_user_cash, user_id)
        date = datetime.datetime.now()
        db.execute("INSERT INTO transactions (user_id, symbol, name, shares, price, total, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   user_id, stock["symbol"], stock["name"], (-1)*shares, stock["price"], (-1)*transistion_value, date)
        flash("Sold!")
        return redirect("/")


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    # User can add cash from here
    if request.method == "GET":
        user_id = session["user_id"]
        return render_template("add.html")
    else:
        new_cash = int(request.form.get("new_cash"))
        if not new_cash:
            return apology("MISSING CASH")
        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]
        updt_cash = user_cash + new_cash
        # Update the cash from the database
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updt_cash, user_id)
