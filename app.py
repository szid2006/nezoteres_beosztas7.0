from flask import Flask, render_template, request, redirect, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = "titkos_jelszo"


# ---------- LOGIN ----------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") == "admin" and request.form.get("password") == "1234":
            session["logged_in"] = True
            return redirect("/shifts")
    return render_template("login.html")


def login_required(fn):
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/")
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


# ---------- SHIFTS ----------
SHIFTS = []
WORKERS = []

ROLES = [
    "Nézőtér beülős",
    "Nézőtér csak csipog",
    "Jolly joker",
    "Ruhatár bal",
    "Ruhatár jobb",
    "Ruhatár erkély"
]


@app.route("/shifts", methods=["GET", "POST"])
@login_required
def shifts():
    if request.method == "POST":
        show = request.form.get("show")
        dt = request.form.get("datetime")

        required = {}
        for role in ROLES:
            count = int(request.form.get(role, 0))
            if count > 0:
                required[role] = count

        SHIFTS.append({
            "show": show,
            "datetime": dt,
            "roles": required
        })

    return render_template("shifts.html", roles=ROLES, shifts=SHIFTS)


# ---------- WORKERS ----------
@app.route("/workers", methods=["GET", "POST"])
@login_required
def workers():
    if request.method == "POST":
       WORKERS.append({
    "name": request.form.get("name"),
    "preferred": request.form.get("preferred"),  # pl. Hamlet
    "is_ek": "is_ek" in request.form,
    "unavailable": request.form.get("unavailable")  # szövegként egyelőre
})


    return render_template("workers.html", workers=WORKERS)


# ---------- RESULT ----------
@app.route("/result")
@login_required
def result():
    return render_template("result.html", shifts=SHIFTS, workers=WORKERS)
