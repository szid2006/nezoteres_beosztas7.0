from flask import Flask, render_template, request, redirect, session, send_file
from datetime import datetime, time
from io import BytesIO
from openpyxl import Workbook, load_workbook

# ======================================================
# SEGÉDFÜGGVÉNYEK
# ======================================================

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


def is_available(worker, shift_dt):
    for start, end in worker["unavailable_parsed"]:
        if start <= shift_dt <= end:
            return False
    return True


# ======================================================
# FLASK APP
# ======================================================

app = Flask(__name__)
app.secret_key = "titkos_jelszo"

WORKERS = []
SHIFTS = []

# ======================================================
# LOGIN
# ======================================================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") == "admin" and request.form.get("password") == "1234":
            session["logged_in"] = True
            return redirect("/import")
    return render_template("login.html")


def login_required(fn):
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/")
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


# ======================================================
# IMPORT – AZ EGYETLEN ADATBEVITEL
# ======================================================

@app.route("/import", methods=["GET", "POST"])
@login_required
def import_excel():
    global WORKERS, SHIFTS

    if request.method == "POST":
        file = request.files["file"]
        wb = load_workbook(file)

        # ---- WORKERS ----
        WORKERS.clear()
        ws_w = wb["WORKERS"]
        for name, preferred, is_ek, unavailable in ws_w.iter_rows(min_row=2, values_only=True):
            WORKERS.append({
                "name": name,
                "preferred": preferred,
                "is_ek": is_ek == "IGEN",
                "unavailable_parsed": parse_unavailability(unavailable)
            })

        # ---- SHIFTS ----
        SHIFTS.clear()
        ws_s = wb["SHIFTS"]
        temp = {}

        for show, dt, role, count in ws_s.iter_rows(min_row=2, values_only=True):
            key = (show, dt)
            if key not in temp:
                temp[key] = {
                    "show": show,
                    "datetime": datetime.strptime(dt, "%Y-%m-%dT%H:%M"),
                    "roles": {}
                }
            temp[key]["roles"][role] = int(count)

        SHIFTS.extend(temp.values())

        return redirect("/generate")

    return render_template("import.html")


# ======================================================
# BEOSZTÁS
# ======================================================

@app.route("/generate")
@login_required
def generate():
    result = []

    work_count = {w["name"]: 0 for w in WORKERS}

    for shift in SHIFTS:
        assigned = {}
        used = set()
        ek_used = False

        for role, needed in shift["roles"].items():
            assigned[role] = []

            for _ in range(needed):
                candidates = []

                for w in WORKERS:
                    if w["name"] in used:
                        continue
                    if not is_available(w, shift["datetime"]):
                        continue
                    if w["is_ek"] and ek_used:
                        continue
                    candidates.append(w)

                if not candidates:
                    break

                def score(w):
                    s = work_count[w["name"]] * 3
                    if w["is_ek"]:
                        s += 8
                    if w["preferred"] == shift["show"] and role == "Nézőtér beülős":
                        s -= 12
                    return s

                chosen = min(candidates, key=score)
                assigned[role].append(chosen["name"])
                used.add(chosen["name"])
                work_count[chosen["name"]] += 1
                if chosen["is_ek"]:
                    ek_used = True

        result.append({
            "show": shift["show"],
            "datetime": shift["datetime"].strftime("%Y-%m-%d %H:%M"),
            "assigned": assigned
        })

    return render_template("result.html", result=result)


# ======================================================
# EXPORT
# ======================================================

@app.route("/export")
@login_required
def export():
    wb = Workbook()
    ws = wb.active
    ws.title = "Beosztás"

    ws.append(["Dátum", "Előadás", "Munkakör", "Név"])

    for r in generate().args[0]:
        for role, names in r["assigned"].items():
            for name in names:
                ws.append([r["datetime"], r["show"], role, name])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name="nezoter_beosztas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
