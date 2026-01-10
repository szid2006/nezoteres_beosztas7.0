from flask import Flask, render_template, request, redirect, url_for
import csv, io
from openpyxl import load_workbook

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    return redirect(url_for("import_data"))

@app.route("/import", methods=["GET", "POST"])
def import_data():
    if request.method == "POST":
        print("POST /import MEGÉRKEZETT")

        if "file" not in request.files:
            return "Nincs feltöltött fájl", 400

        file = request.files["file"]

        if file.filename == "":
            return "Nincs kiválasztott fájl", 400

        filename = file.filename.lower()
        rows = []

        try:
            # ===== CSV =====
            if filename.endswith(".csv"):
                stream = io.StringIO(file.stream.read().decode("utf-8"))
                reader = csv.DictReader(stream)
                rows = list(reader)

            # ===== XLSX =====
            elif filename.endswith(".xlsx"):
                wb = load_workbook(file, data_only=True)
                ws = wb.active

                headers = [cell.value for cell in ws[1]]

                for row in ws.iter_rows(min_row=2, values_only=True):
                    rows.append(dict(zip(headers, row)))

            else:
                return "Csak CSV vagy XLSX fájl tölthető fel", 400

        except Exception as e:
            print("IMPORT HIBA:", e)
            return f"Hiba az import során: {e}", 400

        print("SOROK SZÁMA:", len(rows))
        print("ELSŐ SOR:", rows[0] if rows else "NINCS ADAT")

        return f"Sikeres import: {len(rows)} sor"

    return render_template("import.html")


if __name__ == "__main__":
    app.run(debug=True)
