"""File upload validation, analysis, and cleanup tests."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

from openpyxl import Workbook

from app.core.config import get_settings
from app.db.models import FileMeta
from app.services.files import purge_expired_files


def make_xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Employees"
    for row in rows:
        ws.append(row)
    ws2 = wb.create_sheet("Departments")
    ws2.append(["Dept", "Budget"])
    ws2.append(["HR", 10000])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


SAMPLE_ROWS = [
    ["Name", "Dept", "HireDate", "Salary"],
    ["Alice", "HR", "2021-05-01", 5000],
    ["Bob", "IT", "2020-11-15", 6200],
    ["Carol", "IT", "2022-01-10", 5800],
    ["Dave", None, None, 4000],
    ["Alice", "HR", "2021-05-01", 5000],  # duplicate of row 2
]


def _analyze(client, filename: str, content: bytes, consent: bool = True):
    return client.post(
        "/api/v1/files/analyze",
        files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
        data={"consent": "true" if consent else "false"},
    )


def test_analyze_xlsx(client):
    resp = _analyze(client, "people.xlsx", make_xlsx(SAMPLE_ROWS))
    assert resp.status_code == 200, resp.text
    analysis = resp.json()
    assert analysis["file_type"] == "xlsx"
    assert analysis["sheet_count"] == 2
    names = [s["name"] for s in analysis["sheets"]]
    assert names == ["Employees", "Departments"]

    employees = analysis["sheets"][0]
    assert employees["headers"] == ["Name", "Dept", "HireDate", "Salary"]
    assert employees["duplicate_rows_scanned"] == 1
    salary_col = next(c for c in employees["columns"] if c["name"] == "Salary")
    assert salary_col["inferred_type"] == "number"
    assert salary_col["sample_values"]
    assert analysis["recommendations"]
    assert analysis["notes"]  # honest limitations are surfaced


def test_analyze_csv(client):
    csv_data = b"id,name,amount\n1,Alice,10\n2,Bob,20\n2,Bob,20\n"
    resp = _analyze(client, "sales.csv", csv_data)
    assert resp.status_code == 200
    analysis = resp.json()
    assert analysis["sheet_count"] == 1
    sheet = analysis["sheets"][0]
    assert sheet["headers"] == ["id", "name", "amount"]
    # Sheet label comes from the uploaded filename, never the temp path.
    assert sheet["name"] == "sales"
    assert sheet["duplicate_rows_scanned"] == 1
    amount_col = next(c for c in sheet["columns"] if c["name"] == "amount")
    assert amount_col["inferred_type"] == "number"


def test_analyze_txt_tsv(client):
    tsv = b"name\tqty\nWidget\t3\nGadget\t5\n"
    resp = _analyze(client, "stock.txt", tsv)
    assert resp.status_code == 200
    sheet = resp.json()["sheets"][0]
    assert sheet["headers"] == ["name", "qty"]
    assert sheet["name"] == "stock"


def test_consent_required(client):
    resp = _analyze(client, "sales.csv", b"a,b\n1,2\n", consent=False)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "consent_required"


def test_unsupported_extension_rejected(client):
    resp = _analyze(client, "run.exe", b"MZ\x90\x00")
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "unsupported_file_type"


def test_fake_xlsx_rejected_by_magic_bytes(client):
    resp = _analyze(client, "fake.xlsx", b"this is definitely not a zip file")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_file_structure"


def test_oversized_file_rejected(client, monkeypatch):
    monkeypatch.setenv("SHEETJEDI_MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    try:
        big = b"a,b\n" + b"1,2\n" * 400_000  # ~1.6 MB
        resp = _analyze(client, "big.csv", big)
        assert resp.status_code == 413
        assert resp.json()["error"]["code"] == "file_too_large"
    finally:
        get_settings.cache_clear()


def test_empty_file_rejected(client):
    resp = _analyze(client, "empty.csv", b"")
    assert resp.status_code in (400, 413)


def test_delete_file_analysis(client):
    resp = _analyze(client, "sales.csv", b"a,b\n1,2\n")
    file_id = resp.json()["file_id"]

    del_resp = client.delete(f"/api/v1/files/{file_id}")
    assert del_resp.status_code == 204

    del_again = client.delete(f"/api/v1/files/{file_id}")
    assert del_again.status_code == 404


def test_expired_records_purged(client, db):
    db.add(
        FileMeta(
            original_name="old.csv",
            safe_name="old.csv",
            file_type="csv",
            size_bytes=10,
            status="analyzed",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    db.commit()
    purged = purge_expired_files(db)
    assert purged == 1


def test_xlsm_analysis_notes_macro_limitation(client):
    # An .xlsm built with openpyxl has no real VBA project, but the analyzer
    # must still parse it (same zip structure) and disclose macro limitations.
    xlsx = make_xlsx([["A", "B"], [1, 2]])
    resp = _analyze(client, "macro.xlsm", xlsx)
    assert resp.status_code == 200
    notes = " ".join(resp.json()["notes"]).lower()
    assert "macro" in notes


def test_analysis_json_stored_without_file_content(client, db):
    resp = _analyze(client, "sales.csv", b"a,b\n1,2\n")
    file_id = resp.json()["file_id"]
    meta = db.get(FileMeta, file_id)
    assert meta is not None
    assert meta.expires_at is not None
    assert meta.analysis_json is not None
    # Structured analysis (headers, samples) stored — not the raw file bytes.
    assert "headers" in meta.analysis_json
    assert '"1"' in meta.analysis_json
