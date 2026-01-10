from flask import Flask, render_template, request, redirect, url_for
import csv, io
from openpyxl import load_workbook

app = Flask(__name__)

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
        show_date = show["dátum"][:10]
        show_title = show["cím"]

        for role, needed in rules.items():
            assigned = []

            candidates = []
            for w in workers:
                name = w["név"]
                is_ek = (w.get("ÉK") == "igen")

                if name in used:
                    continue

                # max 1 ÉK
                if is_ek and ek_used:
                    continue

                # jolly joker nem lehet ÉK
                if role == "jolly joker" and is_ek:
                    continue

                # nem ér rá
                if w.get("nem_ér_rá"):
                    dates = [d.strip() for d in w["nem_ér_rá"].split(",")]
                    if show_date in dates:
                        continue

                # nézni akarja
                if w.get("nézni_akar"):
                    wanted = [s.strip() for s in w["nézni_akar"].split(",")]
                    if show_title in wanted:
                        continue

                candidates.append({
                    "név": name,
                    "ÉK": is_ek,
                    "count": assignment_count[name]
                })

            # ROTÁCIÓ + ÉK HÁTRÁNY
            candidates.sort(
                key=lambda x: (
                    x["count"],
                    1 if x["ÉK"] else 0
                )
            )

            for c in candidates:
                if len(assigned) == needed:
                    break

                assigned.append(c["név"])
                used.add(c["név"])
                assignment_count[c["név"]] += 1

                if c["ÉK"]:
                    ek_used = True

            show_block["szerepek"].append({
                "szerep": role,
                "kért": needed,
                "kiosztott": assigned
            })

        schedule.append(show_block)

    return render_template("schedule.html", schedule=schedule, workers=workers)


if __name__ == "__main__":
    app.run(debug=True)
