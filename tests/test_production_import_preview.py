from io import BytesIO
import pytest
from openpyxl import Workbook
from app.database import SessionLocal
from app.models import AuditLog, ProductionRecord
from app.services.production_import_service import build_import_preview

HEADER="operadora;contrato;competencia;data_atendimento;categoria;item;descricao;quantidade;unidade;valor_faturado;valor_pago;valor_glosado;custo;guia;conta;atendimento;paciente_referencia\n"

def test_csv_preview_does_not_persist(cleanup_marker,tmp_path):
    path=tmp_path/"p.csv";path.write_text(HEADER+"X;Y;2026-07;2026-07-10;taxa;Sala;D;1;evento;100;90;10;40;;;;PAC",encoding="utf-8")
    db=SessionLocal();before=db.query(ProductionRecord).count();db.close()
    result=build_import_preview(path,limit=20)
    db=SessionLocal();after=db.query(ProductionRecord).count();db.close()
    assert before==after and result["analyzed_rows"]==1 and result["invalid_rows"]==1
    assert "paciente_referencia" not in result["rows"][0]["data"]

def test_excel_preview_detects_sheets_and_missing(tmp_path):
    path=tmp_path/"p.xlsx";book=Workbook();sheet=book.active;sheet.title="Dados";sheet.append(["item"]);sheet.append(["Sala"]);book.create_sheet("Outra");book.save(path)
    result=build_import_preview(path,limit=20)
    assert result["sheet_names"]==["Dados","Outra"] and result["used_sheet"]=="Dados" and not result["compatible"] and "operadora" in result["missing_required_fields"]

def test_invalid_preview_file(tmp_path):
    path=tmp_path/"bad.txt";path.write_text("x")
    with pytest.raises(ValueError,match="somente CSV") : build_import_preview(path)

@pytest.mark.integration
def test_preview_route_audit_and_permissions(admin_client,readonly_client,cleanup_marker,admin_username):
    response=admin_client.post("/production/imports/preview",files={"file":("p.csv",BytesIO((HEADER+"X;Y;2026-07;2026-07-10;taxa;Sala;D;1;evento;100;90;10;40;;;;P").encode()),"text/csv")})
    assert response.status_code==200 and "Preview" in response.text
    assert readonly_client.get("/production/imports/preview",follow_redirects=False).status_code==403
    db=SessionLocal()
    try:assert db.query(AuditLog).filter(AuditLog.username==admin_username,AuditLog.action=="production_import_preview_executed").count()==1
    finally:db.close()

