from flask import (
    Flask, render_template, request, redirect,
    url_for, send_file, session
)
from openpyxl import load_workbook, Workbook
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import math, random, tempfile

app = Flask(__name__)
app.secret_key = "nagyon_titkos_kulcs"
app.config["SESSION_PERMANENT"] = False   # böngésző bezárásig él

# =====================================================
# FELHASZNÁLÓK
# =====================================================
USERS = {
    "admin": {
        "password": generate_password_hash("admin123"),
        "role": "admin"
    },
    "vezeto": {
        "password": generate_password_hash("vezeto123"),
        "role": "user"
    }
}

# =====================================================
# GLOBÁLIS AUTH
# =====================================================
@app.before_request
def force_login():
    public_paths = ["/login", "/static"]
    if not any(request.path.startswith(p) for p in public_paths):
        if "user" not in session:
            return redirect(url_for("login"))

# =====================================================
# ADATOK
# =====================================================
workers = []
shows = []
schedule = []
assignment_count = {}

ROLE_RULES = {
    9: {
        "nézőtér beülős": 2,
        "nézőtér csipog": 2,
        "ruhatár bal": 2,
        "ruhatár jobb": 1,
        "ruhatár erkély": 1,
        "jolly joker": 1
    },
    8: {
        "nézőtér beülős": 2,
        "nézőtér csipog": 2,
        "ruhatár bal": 2,
        "ruhatár jobb": 1,
        "jolly joker": 1
    }
}

# =====================================================
# SEGÉDEK
# =====================================================
def normalize_date(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10] if value else ""

def normalize_list(value):
    if not value or (isinstance(value, float) and math.isnan(value)):
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]

def import_file(file):
    wb = load_workbook(file, data_only=True)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        rows.append(dict(zip(headers, row)))
    return rows

# =====================================================
# AUTH
# =====================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]

        if user in USERS and check_password_hash(USERS[user]["password"], pwd):
            session.clear()
            session["user"] = user
            session["role"] = USERS[user]["role"]
            return redirect(url_for("index"))

        return render_template("login.html", error="Hibás belépési adatok")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# =====================================================
# OLDALAK
# =====================================================
@app.route("/")
def index():
    return render_template("import.html")

@app.route("/import/workers", methods=["POST"])
def import_workers():
    global workers
    workers = import_file(request.files["file"])
    assignment_count.clear()
    for w in workers:
        assignment_count[w["név"]] = 0
    return redirect(url_for("index"))

@app.route("/import/shows", methods=["POST"])
def import_shows():
    global shows
    shows = import_file(request.files["file"])
    return redirect(url_for("generate_schedule"))

# =====================================================
# BEOSZTÁS
# =====================================================
@app.route("/schedule")
def generate_schedule():
    global schedule
    schedule = []

    for show in shows:
        total = int(show["létszám"])
        rules = ROLE_RULES.get(total)

        show_date = normalize_date(show["dátum"])
        show_title = show["cím"].strip().lower()

        show_block = {
            "cím": show["cím"],
            "dátum": show["dátum"],
            "szerepek": [],
            "hiba": None
        }

        if not rules:
            show_block["hiba"] = f"Nincs szabály {total} főre"
            schedule.append(show_block)
            continue

        used = set()
        ek_used = False
        assigned_roles = {r: [] for r in rules}

        # ===== 1. BEÜLŐS – NÉZNI AKAR ELSŐBBSÉG =====
        for w in random.sample(workers, len(workers)):
            if len(assigned_roles["nézőtér beülős"]) >= rules["nézőtér beülős"]:
                break
            if w["név"] in used:
                continue
            if show_date in normalize_list(w.get("nem_ér_rá")):
                continue
            if show_title not in [s.lower() for s in normalize_list(w.get("nézni_akar"))]:
                continue
            if w.get("ÉK") == "igen" and ek_used:
                continue

            assigned_roles["nézőtér beülős"].append({
                "név": w["név"],
                "watched": True
            })
            used.add(w["név"])
            assignment_count[w["név"]] += 1
            if w.get("ÉK") == "igen":
                ek_used = True

        # ===== 2. BEÜLŐS FELTÖLTÉS, HA NINCS ELÉG =====
        while len(assigned_roles["nézőtér beülős"]) < rules["nézőtér beülős"]:
            eligible = []
            for w in workers:
                if w["név"] in used:
                    continue
                if show_date in normalize_list(w.get("nem_ér_rá")):
                    continue
                if w.get("ÉK") == "igen" and ek_used:
                    continue
                eligible.append(w)

            if not eligible:
                break

            chosen = min(eligible, key=lambda w: assignment_count[w["név"]])
            assigned_roles["nézőtér beülős"].append({
                "név": chosen["név"],
                "watched": False
            })
            used.add(chosen["név"])
            assignment_count[chosen["név"]] += 1
            if chosen.get("ÉK") == "igen":
                ek_used = True

        # ===== 3. TÖBBI SZEREP =====
        for role, needed in rules.items():
            if role == "nézőtér beülős":
                continue

            while len(assigned_roles[role]) < needed:
                eligible = []
                for w in workers:
                    if w["név"] in used:
                        continue
                    if show_date in normalize_list(w.get("nem_ér_rá")):
                        continue
                    if role == "jolly joker" and w.get("ÉK") == "igen":
                        continue
                    if w.get("ÉK") == "igen" and ek_used:
                        continue
                    eligible.append(w)

                if not eligible:
                    break

                chosen = min(eligible, key=lambda w: assignment_count[w["név"]])
                assigned_roles[role].append({
                    "név": chosen["név"],
                    "watched": False
                })
                used.add(chosen["név"])
                assignment_count[chosen["név"]] += 1
                if chosen.get("ÉK") == "igen":
                    ek_used = True

        for role in rules:
            show_block["szerepek"].append({
                "szerep": role,
                "kért": rules[role],
                "kiosztott": assigned_roles[role]
            })

        schedule.append(show_block)

    return render_template("schedule.html", schedule=schedule, workers=workers)

# =====================================================
# STATISZTIKA
# =====================================================
@app.route("/stats")
def stats():
    stats = {}
    for w in workers:
        stats[w["név"]] = {
            "összes": 0,
            "beülős": 0,
            "nézős": 0,
            "ÉK": (w.get("ÉK") == "igen")
        }

    for show in schedule:
        for s in show["szerepek"]:
            for d in s["kiosztott"]:
                stats[d["név"]]["összes"] += 1
                if s["szerep"] == "nézőtér beülős":
                    stats[d["név"]]["beülős"] += 1
                if d.get("watched"):
                    stats[d["név"]]["nézős"] += 1

    return render_template("stats.html", stats=stats)

# =====================================================
# EXPORT
# =====================================================
@app.route("/export/xlsx")
def export_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = "BEOSZTÁS"

    ws.append([
        "Előadás", "Dátum",
        "nézőtér beülős 1", "nézőtér beülős 2",
        "nézőtér csipog 1", "nézőtér csipog 2",
        "jolly joker",
        "ruhatár bal 1", "ruhatár bal 2",
        "ruhatár jobb", "ruhatár erkély"
    ])

    for show in schedule:
        role_map = {
            s["szerep"]: [d["név"] for d in s["kiosztott"]]
            for s in show["szerepek"]
        }

        ws.append([
            show["cím"], show["dátum"],
            *(role_map.get("nézőtér beülős", ["", ""])[:2]),
            *(role_map.get("nézőtér csipog", ["", ""])[:2]),
            role_map.get("jolly joker", [""])[0],
            *(role_map.get("ruhatár bal", ["", ""])[:2]),
            role_map.get("ruhatár jobb", [""])[0],
            role_map.get("ruhatár erkély", [""])[0]
        ])

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    wb.save(tmp.name)
    tmp.close()

    return send_file(tmp.name, as_attachment=True, download_name="beosztas.xlsx")

# =====================================================
# FUTTATÁS
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)
