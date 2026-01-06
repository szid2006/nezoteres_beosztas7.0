from flask import Flask, render_template, request, redirect, session

# ================= SEGÉDFÜGGVÉNYEK =================

def same_day(dt1, dt2):
    return dt1.split("T")[0] == dt2.split("T")[0]


def already_worked_that_day(worker_name, shift, assignments):
    for a in assignments:
        if same_day(a["datetime"], shift["datetime"]):
            for names in a["assigned"].values():
                if worker_name in names:
                    return True
    return False


# ================= FLASK APP =================

app = Flask(__name__)
app.secret_key = "titkos_jelszo"


# ================= LOGIN =================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (
            request.form.get("username") == "admin"
            and request.form.get("password") == "1234"
        ):
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


# ================= ADATOK =================

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


# ================= SHIFTS =================

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


# ================= WORKERS =================

@app.route("/workers", methods=["GET", "POST"])
@login_required
def workers():
    if request.method == "POST":
        WORKERS.append({
            "name": request.form.get("name"),
            "preferred": request.form.get("preferred"),
            "is_ek": "is_ek" in request.form,
            "unavailable": request.form.get("unavailable")
        })

    return render_template("workers.html", workers=WORKERS)


# ================= BEOSZTÓ LOGIKA =================

def generate_schedule(shifts, workers):
    assignments = []

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

                    if already_worked_that_day(name, shift, assignments):
                        continue

                    if w["is_ek"]:
                        if ek_used or role == "Jolly joker":
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


# ================= GENERATE ROUTE =================

@app.route("/generate")
@login_required
def generate():
    result = generate_schedule(SHIFTS, WORKERS)
    return render_template("result.html", result=result)
