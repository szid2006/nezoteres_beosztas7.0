from flask import Flask, render_template, request, redirect, url_for
import csv, io
from openpyxl import load_workbook

app = Flask(__name__)

workers = []
shows = []
schedule = []

ROLE_RULES = {
    9: {
        "nézőtér beülős": 2,
        "nézőtér csipog": 2,
        "ruhatár bal": 2,
        "ruhatár jobb": 1,
        "ruhatár erkély": 1
    },
    8: {
        "nézőtér beülős": 2,
        "nézőtér csipog": 2,
        "ruhatár bal": 2,
        "ruhatár jobb": 1
    }
}


# ===== IMPORT =====
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


@app.route("/")
def index():
    return render_template("import.html")


@app.route("/import/workers", methods=["POST"])
def import_workers():
    global workers
    workers = import_file(request.files["file"])
    return redirect(url_for("index"))


@app.route("/import/shows", methods=["POST"])
def import_shows():
    global shows
    shows = import_file(request.files["file"])
    return redirect(url_for("generate_schedule"))


# ===== BEOSZTÁS GENERÁLÁS =====
@app.route("/schedule")
def generate_schedule():
    global schedule
    schedule = []

    for show in shows:
        total = int(show["létszám"])
        rules = ROLE_RULES.get(total)

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

        available_workers = [w["név"] for w in workers]
        used = set()

        for role, needed in rules.items():
            assigned = []

            for name in available_workers:
                if name not in used and len(assigned) < needed:
                    assigned.append(name)
                    used.add(name)

            show_block["szerepek"].append({
                "szerep": role,
                "kért": needed,
                "kiosztott": assigned
            })

        schedule.append(show_block)

    return render_template("schedule.html", schedule=schedule)
