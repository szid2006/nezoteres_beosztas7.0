from flask import Flask, render_template, request, redirect, session
from datetime import datetime
def same_day(dt1, dt2):
    return dt1.split("T")[0] == dt2.split("T")[0]


def already_worked_that_day(worker_name, shift, assignments):
    for a in assignments:
        if same_day(a["datetime"], shift["datetime"]):
            if worker_name in a["assigned"].values():
                return True
    return False


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
ROLE_LIMITS = {
    "Nézőtér beülős": 2,
    "Nézőtér csak csipog": 2,
    "Jolly joker": 1,
    "Ruhatár bal": 2,
    "Ruhatár jobb": 1,
    "Ruhatár erkély": 1
}



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
    @app.route("/generate")
@login_required
    def generate_schedule(shifts, workers):
    assignments = []

    # statisztika
    work_count = {w["name"]: 0 for w in workers}
    role_history = {w["name"]: [] for w in workers}

    for shift in shifts:
        assigned = {}
        ek_used = False

        for role, needed in shift["roles"].items():
            assigned[role] = []

            for _ in range(needed):
                candidates = []

                for w in workers:
                    name = w["name"]

                    # napi duplázás tiltás
                    if already_worked_that_day(name, shift, assignments):
                        continue

                    # ÉK szabály
                    if w["is_ek"]:
                        if ek_used:
                            continue
                        if role == "Jolly joker":
                            continue

                    candidates.append(w)

                if not candidates:
                    continue

                def score(w):
                    s = work_count[w["name"]] * 2
                    s += role_history[w["name"]].count(role)

                    if w["is_ek"]:
                        s += 5

                    if w["preferred"] == shift["show"] and role == "Nézőtér beülős":
                        s -= 10

                    return s

                chosen = min(candidates, key=score)

                assigned[role].append(chosen["name"])
                work_count[chosen["name"]] += 1
                role_history[chosen["name"]].append(role)

                if chosen["is_ek"]:
                    ek_used = True

        assignments.append({
            "show": shift["show"],
            "datetime": shift["datetime"],
            "assigned": assigned
        })

    return assignments

def generate():
    result = generate_schedule(SHIFTS, WORKERS)
    return render_template("result.html", result=result)

