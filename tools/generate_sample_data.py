"""Generates the fictional Vela Devices sample data: setup SQL with inline rows, plus spec-sheet PDFs.
Re-run to regenerate:  python3 tools/generate_sample_data.py   (needs reportlab)
Planted problems the demo should find:
  - 3 GA SKUs with no BOM (CM-30, SN-AIR, AC-MNT); 3 SKUs with BOMs not updated in over a year
  - GA SKUs CB-OBD and CB-PWR use an obsolete fuse; CM-10 and CM-20 use an NRND image sensor
  - 4 spec sheets that disagree with the SKU table (weight, max temp, IP rating, lifecycle)
"""
import json, os, random
from datetime import date, timedelta

random.seed(7)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OWNERS = [
    ("Gateways", "Priya Nair", "priya.nair@veladevices.example"),
    ("Cameras", "Marcus Lee", "marcus.lee@veladevices.example"),
    ("Sensors", "Elena Torres", "elena.torres@veladevices.example"),
    ("Cables", "Sam Okoro", "sam.okoro@veladevices.example"),
    ("Accessories", "Sam Okoro", "sam.okoro@veladevices.example"),
    ("Licenses", "Dana Kim", "dana.kim@veladevices.example"),
]

# sku, name, line, lifecycle, launch, price, weight_g, tmin, tmax, ip
SKUS = [
    ("GW-100", "Vela Gateway 100", "Gateways", "EOL", "2021-03-01", 249, 310, -30, 70, "IP67"),
    ("GW-200", "Vela Gateway 200", "Gateways", "GA", "2023-05-15", 299, 295, -40, 85, "IP67"),
    ("GW-300", "Vela Gateway 300 LTE", "Gateways", "GA", "2025-02-10", 349, 280, -40, 85, "IP68"),
    ("GW-400", "Vela Gateway 400 5G", "Gateways", "NPI", "2026-11-01", 449, 300, -40, 85, "IP68"),
    ("CM-10", "Vela Dash Cam 10", "Cameras", "GA", "2022-08-01", 199, 180, -20, 70, "IP54"),
    ("CM-20", "Vela Dual Cam 20", "Cameras", "GA", "2024-04-20", 299, 240, -20, 70, "IP54"),
    ("CM-30", "Vela AI Cam 30", "Cameras", "GA", "2025-09-01", 399, 260, -30, 75, "IP65"),
    ("CM-40", "Vela Site Cam 40", "Cameras", "NPI", "2026-12-01", 499, 620, -30, 60, "IP66"),
    ("SN-TEMP", "Vela Temp Sensor", "Sensors", "GA", "2022-01-10", 59, 45, -40, 85, "IP67"),
    ("SN-DOOR", "Vela Door Sensor", "Sensors", "GA", "2022-06-01", 49, 38, -30, 70, "IP65"),
    ("SN-TPMS", "Vela Tire Sensor", "Sensors", "GA", "2024-10-15", 89, 30, -40, 125, "IP69K"),
    ("SN-AIR", "Vela Air Quality Sensor", "Sensors", "GA", "2025-06-01", 129, 95, -20, 60, "IP54"),
    ("CB-OBD", "OBD-II Harness", "Cables", "GA", "2021-03-01", 29, 120, -40, 105, None),
    ("CB-J1939", "J1939 Heavy Duty Harness", "Cables", "GA", "2021-03-01", 39, 160, -40, 105, None),
    ("CB-CAM", "Camera Extension Cable 3m", "Cables", "GA", "2022-08-01", 19, 90, -30, 85, None),
    ("CB-PWR", "Hardwire Power Cable", "Cables", "GA", "2021-03-01", 15, 70, -40, 105, None),
    ("AC-MNT", "Windshield Mount", "Accessories", "GA", "2022-08-01", 12, 40, None, None, None),
    ("AC-ANT", "External LTE Antenna", "Accessories", "GA", "2023-05-15", 35, 85, -40, 85, "IP67"),
    ("AC-PWR", "Power Supply Unit", "Accessories", "EOL", "2020-11-01", 25, 150, 0, 40, None),
    ("LC-BASIC", "Telematics Basic License", "Licenses", "GA", "2021-03-01", 25, None, None, None, None),
    ("LC-PRO", "Video Pro License", "Licenses", "GA", "2023-01-01", 40, None, None, None, None),
]
HARDWARE = [s for s in SKUS if s[2] in ("Gateways", "Cameras", "Sensors")]

COMPONENTS = [
    ("C-MCU-01", "ARM Cortex-M4 MCU", "Kestrel Semi", 3.10, "Active"),
    ("C-MCU-02", "ARM Cortex-M33 MCU", "Kestrel Semi", 3.80, "Active"),
    ("C-MDM-4G", "LTE Cat-1 modem", "Northline RF", 14.50, "Active"),
    ("C-MDM-3G", "3G modem", "Northline RF", 11.00, "Obsolete"),
    ("C-MDM-5G", "5G RedCap modem", "Northline RF", 29.00, "Active"),
    ("C-GNSS", "GNSS receiver", "Orbitline", 4.20, "Active"),
    ("C-IMG-2M", "2MP image sensor", "Lumasense", 6.80, "NRND"),
    ("C-IMG-5M", "5MP image sensor", "Lumasense", 9.40, "Active"),
    ("C-NPU", "Edge AI accelerator", "Cortiq", 18.00, "Active"),
    ("C-BAT-L", "Li-ion backup battery", "Voltcore", 5.10, "Active"),
    ("C-BAT-C", "Coin cell CR2477", "Voltcore", 0.60, "Active"),
    ("C-ENC-A", "Aluminum enclosure", "Forma Metals", 7.20, "Active"),
    ("C-ENC-P", "Polycarbonate enclosure", "Forma Plastics", 2.40, "Active"),
    ("C-BLE", "BLE 5.2 radio", "Northline RF", 2.10, "Active"),
    ("C-TMP", "Temperature sensor IC", "Senseon", 0.90, "Active"),
    ("C-PRS", "Pressure sensor IC", "Senseon", 2.30, "Active"),
    ("C-GAS", "VOC gas sensor", "Senseon", 7.60, "Active"),
    ("C-REED", "Reed switch", "Senseon", 0.40, "Active"),
    ("C-CONN-16", "16-pin connector", "Linkwell", 1.20, "Active"),
    ("C-CONN-9", "9-pin Deutsch connector", "Linkwell", 2.60, "Active"),
    ("C-WIRE", "18 AWG harness wire (m)", "Linkwell", 0.35, "Active"),
    ("C-LENS", "Wide-angle lens", "Lumasense", 3.90, "Active"),
    ("C-IR", "IR LED array", "Lumasense", 1.70, "Active"),
    ("C-FUSE", "Inline fuse", "Linkwell", 0.30, "Obsolete"),
]

RECIPES = {
    "GW-100": ["C-MCU-01", "C-MDM-3G", "C-GNSS", "C-BAT-L", "C-ENC-P", "C-CONN-16"],
    "GW-200": ["C-MCU-01", "C-MDM-4G", "C-GNSS", "C-BAT-L", "C-ENC-A", "C-CONN-16", "C-BLE"],
    "GW-300": ["C-MCU-02", "C-MDM-4G", "C-GNSS", "C-BAT-L", "C-ENC-A", "C-CONN-16", "C-BLE"],
    "CM-10": ["C-MCU-01", "C-IMG-2M", "C-LENS", "C-IR", "C-ENC-P"],
    "CM-20": ["C-MCU-02", "C-IMG-2M", "C-IMG-5M", "C-LENS", "C-IR", "C-ENC-P"],
    "SN-TEMP": ["C-BLE", "C-TMP", "C-BAT-C", "C-ENC-P"],
    "SN-DOOR": ["C-BLE", "C-REED", "C-BAT-C", "C-ENC-P"],
    "SN-TPMS": ["C-BLE", "C-PRS", "C-TMP", "C-BAT-C"],
    "CB-OBD": ["C-CONN-16", "C-WIRE", "C-FUSE"],
    "CB-J1939": ["C-CONN-9", "C-WIRE"],
    "CB-CAM": ["C-CONN-16", "C-WIRE"],
    "CB-PWR": ["C-WIRE", "C-FUSE"],
    "AC-ANT": ["C-CONN-16", "C-ENC-P"],
    "AC-PWR": ["C-ENC-P", "C-FUSE"],
}
# CM-30, SN-AIR and AC-MNT are GA but have no recipe, so they get no BOM (planted gap).
STALE = {"CB-J1939": "2024-02-12", "SN-DOOR": "2024-06-30", "CM-10": "2025-01-20"}

def bom_rows():
    rows = []
    for sku, comps in RECIPES.items():
        updated = STALE.get(sku, (date(2026, 3, 1) + timedelta(days=random.randint(0, 200))).isoformat())
        rev = "B" if sku in STALE else random.choice(["C", "D", "E"])
        for c in comps:
            qty = 2 if c in ("C-WIRE",) else 1
            rows.append((sku, c, qty, rev, updated))
    return rows

# Spec sheet values; differences from SKUS are the planted mismatches.
SPEC_OVERRIDES = {
    "GW-200": {"weight_g": 325},             # sheet says 325 g, table says 295 g
    "CM-20": {"op_temp_max_c": 60},           # sheet 60 C, table 70 C
    "SN-TPMS": {"ip_rating": "IP67"},         # sheet IP67, table IP69K
    "CM-10": {"lifecycle_status": "EOL"},     # sheet says End of Life, table says GA
}

def sql_str(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"

def values(rows):
    return ",\n  ".join("(" + ", ".join(sql_str(v) for v in r) + ")" for r in rows)

def write_sql():
    owners = values(OWNERS)
    skus = values(SKUS)
    comps = values(COMPONENTS)
    boms = values(bom_rows())
    sql = f"""-- Product Data Copilot, step 1: raw enterprise data (fictional company: Vela Devices).
-- Generated by tools/generate_sample_data.py. Run in the Databricks SQL editor.

CREATE SCHEMA IF NOT EXISTS workspace.product_data;
USE workspace.product_data;

-- Volume for the spec-sheet PDFs (upload the files in spec_sheets/ here after running this).
CREATE VOLUME IF NOT EXISTS workspace.product_data.spec_sheets;

CREATE OR REPLACE TABLE product_line_owners (product_line STRING, owner_name STRING, owner_email STRING)
COMMENT 'Who owns data quality for each product line.';
INSERT INTO product_line_owners VALUES
  {owners};

CREATE OR REPLACE TABLE skus (
  sku STRING, product_name STRING, product_line STRING, lifecycle_status STRING, launch_date STRING,
  list_price_usd DOUBLE, weight_g INT, op_temp_min_c INT, op_temp_max_c INT, ip_rating STRING)
COMMENT 'SKU master from the PLM system. lifecycle_status is NPI, GA or EOL.'
TBLPROPERTIES (delta.enableChangeDataFeed = true);
INSERT INTO skus VALUES
  {skus};

CREATE OR REPLACE TABLE components (
  component_id STRING, description STRING, supplier STRING, unit_cost_usd DOUBLE, lifecycle STRING)
COMMENT 'Component catalog. lifecycle is Active, NRND (not recommended for new designs) or Obsolete.';
INSERT INTO components VALUES
  {comps};

CREATE OR REPLACE TABLE bom_lines (
  sku STRING, component_id STRING, qty INT, bom_revision STRING, last_updated STRING)
COMMENT 'Bill of materials lines per SKU.';
INSERT INTO bom_lines VALUES
  {boms};

-- Tasks the copilot creates for data owners.
CREATE TABLE IF NOT EXISTS data_fix_tasks (
  sku STRING, issue STRING, proposed_fix STRING, owner_email STRING, created_at TIMESTAMP, status STRING);

-- A couple of edits so the change history (Delta Change Data Feed) has something to show.
UPDATE skus SET list_price_usd = 329 WHERE sku = 'GW-300';
UPDATE skus SET list_price_usd = 119 WHERE sku = 'SN-AIR';
"""
    open(os.path.join(ROOT, "sql", "01_raw_data.sql"), "w").write(sql)

def spec_for(s):
    sku, name, line, life, launch, price, w, tmin, tmax, ip = s
    spec = {"sku": sku, "product_name": name, "weight_g": w, "op_temp_min_c": tmin,
            "op_temp_max_c": tmax, "ip_rating": ip, "lifecycle_status": life}
    spec.update(SPEC_OVERRIDES.get(sku, {}))
    return spec

def write_pdfs():
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    st = getSampleStyleSheet()
    truth = []
    life_text = {"GA": "Generally available", "NPI": "New product introduction (pre-launch)", "EOL": "End of Life. Last order date has passed."}
    blurbs = {"Gateways": "Rugged telematics gateway for fleet vehicles with GNSS tracking and cellular backhaul.",
              "Cameras": "Vehicle camera for road and driver visibility with on-device event detection.",
              "Sensors": "Battery-powered wireless sensor that reports to a Vela gateway over BLE."}
    for s in HARDWARE:
        spec = spec_for(s)
        truth.append(spec)
        path = os.path.join(ROOT, "spec_sheets", f"{spec['sku']}_spec_sheet.pdf")
        doc = SimpleDocTemplate(path, pagesize=letter, title=f"{spec['product_name']} Spec Sheet")
        rows = [["Specification", "Value"],
                ["Model / SKU", spec["sku"]],
                ["Weight", f"{spec['weight_g']} g"],
                ["Operating temperature", f"{spec['op_temp_min_c']} °C to {spec['op_temp_max_c']} °C"],
                ["Ingress protection", spec["ip_rating"] or "Not rated"],
                ["Product status", life_text[spec["lifecycle_status"]]]]
        t = Table(rows, colWidths=[200, 260])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
        doc.build([Paragraph("Vela Devices", st["Normal"]),
                   Paragraph(f"{spec['product_name']} Spec Sheet", st["Title"]),
                   Paragraph(blurbs[s[2]], st["Normal"]), Spacer(1, 14), t, Spacer(1, 14),
                   Paragraph("Specifications are subject to change. Fictional product for demonstration.", st["Italic"])])
    json.dump(truth, open(os.path.join(ROOT, "tools", "spec_sheet_values.json"), "w"), indent=1)
    rows = [(f"{s['sku']}_spec_sheet.pdf", s["sku"], s["weight_g"], s["op_temp_min_c"], s["op_temp_max_c"],
             s["ip_rating"], s["lifecycle_status"]) for s in truth]
    open(os.path.join(ROOT, "sql", "02b_fallback_spec_values.sql"), "w").write(f"""-- Fallback for step 2: use this only if ai_parse_document / ai_extract are not available in your workspace.
-- It loads the same values the spec-sheet PDFs contain, so steps 3 onward work unchanged.
USE workspace.product_data;

CREATE OR REPLACE TABLE spec_extracted (
  source_file STRING, sku STRING, weight_g INT, op_temp_min_c INT, op_temp_max_c INT,
  ip_rating STRING, lifecycle_status STRING)
COMMENT 'Specs extracted from spec-sheet PDFs (fallback: loaded directly, not parsed).';
INSERT INTO spec_extracted VALUES
  {values(rows)};
""")

if __name__ == "__main__":
    write_sql()
    write_pdfs()
    print("wrote sql/01_raw_data.sql and", len(HARDWARE), "PDFs")
