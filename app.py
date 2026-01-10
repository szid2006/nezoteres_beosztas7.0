from flask import Flask, render_template, request, redirect, url_for
from openpyxl import load_workbook
from datetime import datetime
import csv, io, math, random

app = Flask(__name__)

# ================== ADATOK ==================
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

# ================== SEGÉDEK ==================
def normalize_date(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if value is None:
        return ""
    return str(value)[:10]

def normalize_list(value):
    if value is None:
        return []
    if isinstance(value, float) and math.isnan(value):
        return []
    text = str(value).strip()
    if text.lower() in ("", "none", "nan"):
        return []
    return [v.strip() for v in text.split(",") if v.strip()]

def import_file(file):
    filename = file.filename.lower()
    rows = []

    if filename.endswith(".csv"):
        stream = io.StringIO(file.stream.read().decode("utf-8"))
        rows = list(csv.DictReader(stream))

    elif filename.endswith(".xlsx"):
        wb = load_workbook(file, data_only=True)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        for row in ws.iter_rows(min_row=2, values_only=True):
            rows.append(dict(zip(headers, row)))

    return rows

# ================== ROUTES ==================
@app.route("/")
def index():
    return render_template("import.html")

@app.route("/import/workers", methods=["POST"])
def import_workers():
    global workers
    workers = import_file(request.files["file"])
    for w in workers:
        assignment_count.setdefault(w["név"], 0)
    return redirect(url_for("index"))

@app.route("/import/shows", methods=["POST"])
def import_shows():
    global shows
    shows = import_file(request.files["file"])
    return redirect(url_for("generate_schedule"))

@app.route("/schedule")
def generate_schedule():
    global schedule
    schedule = []

    for show in shows:
        total = int(show["létszám"])
        rules = ROLE_RULES.get(total)

        show_date = normalize_date(show["dátum"])
        show_title = show["cím"]

        show_block = {
            "cím": show_title,
            "dátum": show["dátum"],
            "szerepek": [],
            "hiba": None
        }

        if not rules:
            show_block["hiba"] = f"Nincs szabály {total} főre"
            schedule.append(show_block)
            continue

        used = set()
        ek_used = False  # 🔒 MAX 1 ÉK / ELŐADÁS

        for role, needed in rules.items():
            assigned = []

            # -------- HARD FILTER --------
            eligible = []
            for w in workers:
                name = w["név"]
                is_ek = str(w.get("ÉK")).lower() == "igen"

                if name in used:
                    continue
                if is_ek and ek_used:
                    continue
                if role == "jolly joker" and is_ek:
                    continue
                if show_date in normalize_list(w.get("nem_ér_rá")):
                    continue
                if show_title in normalize_list(w.get("nézni_akar")):
                    continue

                eligible.append({
                    "név": name,
                    "ÉK": is_ek,
                    "count": assignment_count[name]
                })

            # -------- SÚLYOZOTT RANDOM --------
            for _ in range(needed):
                if not eligible:
                    break

                weights = [
                    (1 / (c["count"] + 1)) * (0.3 if c["ÉK"] else 1.0)
                    for c in eligible
                ]

                chosen = random.choices(eligible, weights=weights, k=1)[0]

                assigned.append(chosen["név"])
                used.add(chosen["név"])
                assignment_count[chosen["név"]] += 1

                if chosen["ÉK"]:
                    ek_used = True

                eligible = [c for c in eligible if c["név"] != chosen["név"]]

            show_block["szerepek"].append({
                "szerep": role,
                "kért": needed,
                "kiosztott": assigned
            })

        schedule.append(show_block)

    return render_template("schedule.html", schedule=schedule, workers=workers)

if __name__ == "__main__":
    app.run(debug=True)
