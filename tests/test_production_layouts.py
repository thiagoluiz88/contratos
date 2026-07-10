from datetime import date

import pytest
from openpyxl import Workbook

from app.database import SessionLocal
from app.models import AuditLog, ProductionImportBatch, ProductionRecord
from app.services.production_import_service import create_import_batch, import_file_to_batch, parse_csv
from app.services.production_layout_service import TARGET_FIELDS, apply_layout_mapping, build_layout_preview, create_layout, validate_layout


def mappings(prefix="COL"):
    return [{"target_field": field, "source_column": f"{prefix}_{index}", "required": index < 13} for index, field in enumerate(TARGET_FIELDS)]


@pytest.mark.integration
def test_layout_validation_mapping_and_csv_import(cleanup_marker, tmp_path):
    layout = create_layout(name=f"Layout {cleanup_marker}", source_system="outro", source_type="csv", delimiter=";", encoding="utf-8", has_header=True, status="ativo", mappings=mappings(), created_by=cleanup_marker.lower())
    db = SessionLocal()
    try:
        persisted = db.get(type(layout), layout.id)
        assert validate_layout(persisted)["valid"]
        source = {f"COL_{index}": value for index, value in enumerate(["Sem vínculo", "Contrato X", "2026-07", "2026-07-10", "taxa", "Sala", "Descrição", "2", "evento", "200", "180", "20", "80", "G", "C", "A", "P"])}
        mapped = apply_layout_mapping(source, persisted)
        assert mapped["competencia"] == "2026-07" and mapped["valor_pago"] == "180"
        preview = build_layout_preview([{**source, "IGNORADA": "x"}], persisted)
        assert preview["unmapped_columns"] == ["IGNORADA"]
    finally: db.close()
    path = tmp_path / "mapped.csv"
    path.write_text(";".join(source.keys()) + "\n" + ";".join(source.values()), encoding="utf-8")
    batch, _ = create_import_batch(batch_name=f"Mapeado {cleanup_marker}", source_type="csv", source_system="outro", file_path=str(path), layout_id=layout.id)
    processed, _ = import_file_to_batch(batch.id, path)
    assert processed.valid_rows == 0 and processed.invalid_rows == 1  # vínculos inexistentes viram pendência
    assert processed.import_summary_json["layout_id"] == layout.id
    assert processed.import_summary_json["ignored_columns"] == []


def test_layout_rejects_missing_required_fields(cleanup_marker):
    with pytest.raises(ValueError, match="obrigatórios"):
        create_layout(name=f"Inválido {cleanup_marker}", source_system="planilha", source_type="csv", delimiter=";", encoding="utf-8", has_header=True, status="ativo", mappings=[{"target_field": "item", "source_column": "Item"}])


@pytest.mark.integration
def test_excel_first_sheet_uses_same_layout(cleanup_marker, tmp_path):
    layout = create_layout(name=f"Excel {cleanup_marker}", source_system="planilha", source_type="excel", delimiter=None, encoding=None, has_header=True, status="ativo", mappings=mappings("X"))
    path = tmp_path / "production.xlsx"
    workbook = Workbook(); sheet = workbook.active
    sheet.append([f"X_{index}" for index in range(len(TARGET_FIELDS))])
    sheet.append(["Sem vínculo", "Contrato", "2026-07", date(2026, 7, 10), "taxa", "Sala", "Desc", 1, "evento", 100, 90, 10, 40, None, None, None, None])
    workbook.create_sheet("Ignorada"); workbook.save(path)
    batch, _ = create_import_batch(batch_name=f"Excel lote {cleanup_marker}", source_type="excel", source_system="planilha", file_path=str(path), layout_id=layout.id)
    processed, events = import_file_to_batch(batch.id, path)
    assert processed.total_rows == 1
    assert any(event.action == "production_excel_file_imported" for event in events)


@pytest.mark.integration
def test_layout_routes_permissions_and_audit(admin_client, readonly_client, cleanup_marker, admin_username):
    data = {"name": f"Rota {cleanup_marker}", "source_system": "planilha", "source_type": "csv", "delimiter": ";", "encoding": "utf-8", "has_header": "on", "status": "rascunho"}
    response = admin_client.post("/production/layouts", data=data, follow_redirects=False)
    assert response.status_code == 303
    layout_id = int(response.headers["location"].split("/")[-1])
    assert readonly_client.get("/production/layouts").status_code == 200
    assert readonly_client.get(f"/production/layouts/{layout_id}").status_code == 200
    assert readonly_client.get("/production/layouts/new", follow_redirects=False).status_code == 403
    db = SessionLocal()
    try:
        assert db.query(AuditLog).filter(AuditLog.username == admin_username, AuditLog.action == "production_import_layout_created", AuditLog.entity_id == layout_id).count() == 1
    finally: db.close()

