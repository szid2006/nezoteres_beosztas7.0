from flask import Flask, render_template, request, redirect, url_for
import csv, io
from openpyxl import load_workbook

app = Flask(__name__)

# ================== TÁROLÓK ==================
workers = []
shows = []
schedule = []


# ================== SEGÉDFÜGGVÉNY ==================
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

    else:
        raise ValueError("Csak CSV vagy XLSX tölthető fel")

    return rows


# ================== OLDALAK ==================
@app.route("/")
def index():
    return render_template("import.html")


# ================== DOLGOZÓK IMPORT ==================
@app.route("/import/workers", methods=["POST"])
def import_workers():
    global workers
    file = request.files.get("file")
    workers = import_file(file)
    return redirect(url_for("index"))


# ================== ELŐADÁSOK IMPORT ==================
@app.route("/import/shows", methods=["POST"])
def import_shows():
    global shows
    file = request.files.get("file")
    shows = import_file(file)
    return redirect(url_for("generate_schedule"))


# ================== BEOSZTÁS GENERÁLÁS ==================
@app.route("/schedule")
def generate_schedule():
    global schedule
    schedule = []

    worker_index = 0

    for show in shows:
        needed = int(show["létszám"])
        assigned = []

        for _ in range(needed):
            if worker_index >= len(workers):
                break
            assigned.append(workers[worker_index]["név"])
            worker_index += 1

        schedule.append({
            "cím": show["cím"],
            "dátum": show["dátum"],
            "dolgozók": assigned
        })

    return render_template("schedule.html", schedule=schedule)


if __name__ == "__main__":
    app.run(debug=True)
