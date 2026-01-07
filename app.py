from flask import Flask, render_template, request, redirect, session, send_file
from datetime import datetime, time
from io import BytesIO
from openpyxl import Workbook, load_workbook

# ======================================================
# SEGÉDFÜGGVÉNYEK
# ======================================================

def same_day(dt1, dt2):
    return dt1.split("T")[0] == dt2.split("T")[0]


def parse_unavailability(text):
    periods = []
    if not text:
        return periods

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if len(line) == 10:
            d = datetime.strptime(line, "%Y-%m-%d").date()
            periods.append((
                datetime.combine(d, time(0, 0)),
                datetime.combine(d, time(23, 59))
            ))
        else:
            date_part, time_part = line.split()
            start_t, end_t = time_part.split("-")
            d = datetime.strptime(date_part, "%Y-%m-%d").date()
            start = datetime.combine(d, datetime.strptime(start_t, "%H:%M").time())
            end = datetime.combine(d, datetime.strptime(end_t, "%H:%M").time())
            periods.append((start, end))
    return periods


def is_available(worker, shift_datetime):
    shift_dt = datetime.strptime(shift_datetime, "%Y-%m-%dT%H:%M")
    for start, end in worker["unavailable_parsed"]:
        if start <= shift_dt <= end:
            return False
    return True


def already_worked_that_day(worker_name, shift, assignments):
    for a in assignments:
        if same_day(a["datetime"], shift["datetime"]):
            for names in a["assigned"].values():
                if worker_name in names:
                    return True
    return False


# ======================================================
# FLASK APP
# ======================================================

app = Flask(__name__)
app.secret_key = "titkos_jelszo"

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

# ======================================================
# LOGIN
# ======================================================

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


# ======================================================
# SHIFTS
# ======================================================

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


# ======================================================
# WORKERS
# ======================================================

@app.route("/workers", methods=["GET", "POST"])
@login_required
def workers():
    if request.method == "POST":
        raw_unavailable = request.form.get("unavailable")

        WORKERS.append({
            "name": request.form.get("name"),
            "preferred": request.form.get("preferred"),
            "is_ek": "is_ek" in request.form,
            "unavailable_raw": raw_unavailable,
            "unavailable_parsed": parse_unavailability(raw_unavailable)
        })

    return render_template("workers.html", workers=WORKERS)


# ======================================================
# BEOSZTÓ LOGIKA
# ======================================================

def generate_schedule(shifts, workers):
    assignments = []
    work_count = {w["name"]: 0 for w in workers}
    role_history = {w["name"]: [] for w in workers}

    for shift in shifts:
        assigned = {}
        used_in_shift = set()
        ek_used = False

        for role, needed in shift["roles"].items():
            assigned[role] = []

            for _ in range(needed):
                candidates = []

                for w in workers:
                    name = w["name"]
                    if name in used_in_shift:
                        continue
                    if not is_available(w, shift["datetime"]):
                        continue
                    if already_worked_that_day(name, shift, assignments):
                        continue
                    if w["is_ek"] and (ek_used or role == "Jolly joker"):
                        continue
                    candidates.append(w)

                if not candidates:
                    break

                def score(w):
                    s = work_count[w["name"]] * 3
                    s += role_history[w["name"]].count(role) * 2
                    if w["is_ek"]:
                        s += 8
                    if w["preferred"] == shift["show"] and role == "Nézőtér beülős":
                        s -= 12
                    return s

                chosen = min(candidates, key=score)
                assigned[role].append(chosen["name"])
                used_in_shift.add(chosen["name"])
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


# ======================================================
# GENERATE
# ======================================================

@app.route("/generate")
@login_required
def generate():
    result = generate_schedule(SHIFTS, WORKERS)
    return render_template("result.html", result=result)


# ======================================================
# EXPORT
# ======================================================

@app.route("/export")
@login_required
def export_excel():
    result = generate_schedule(SHIFTS, WORKERS)

    wb = Workbook()
    ws = wb.active
    ws.title = "Beosztás"
    ws.append(["Dátum", "Előadás", "Munkakör", "Név", "ÉK"])

    for shift in result:
        for role, names in shift["assigned"].items():
            for name in names:
                worker = next(w for w in WORKERS if w["name"] == name)
                ws.append([
                    shift["datetime"],
                    shift["show"],
                    role,
                    name,
                    "IGEN" if worker["is_ek"] else ""
                ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="nezoter_beosztas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ======================================================
# IMPORT
# ======================================================

@app.route("/import", methods=["GET", "POST"])
@login_required
def import_excel():
    global SHIFTS, WORKERS

    if request.method == "POST":
        file = request.files["file"]
        wb = load_workbook(file)

        # ---- WORKERS ----
        WORKERS.clear()
        ws_w = wb["WORKERS"]
        for row in ws_w.iter_rows(min_row=2, values_only=True):
            name, preferred, is_ek, unavailable = row
            WORKERS.append({
                "name": name,
                "preferred": preferred,
                "is_ek": is_ek == "IGEN",
                "unavailable_raw": unavailable,
                "unavailable_parsed": parse_unavailability(unavailable)
            })

        # ---- SHIFTS ----
        SHIFTS.clear()
        ws_s = wb["SHIFTS"]
        temp = {}

        for show, dt, role, count in ws_s.iter_rows(min_row=2, values_only=True):
            key = (show, dt)
            if key not in temp:
                temp[key] = {"show": show, "datetime": dt, "roles": {}}
            temp[key]["roles"][role] = count

        SHIFTS.extend(temp.values())

        return redirect("/generate")

    return render_template("import.html")
