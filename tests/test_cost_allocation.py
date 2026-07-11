from datetime import date
from decimal import Decimal
import pytest
from app.database import SessionLocal
from app.models import AuditLog, ProductionImportBatch, ProductionRecord
from app.services.cost_allocation_service import create_allocation_rule,create_cost_center,estimate_indirect_cost_for_record,update_cost_center

@pytest.mark.integration
def test_centers_rules_and_estimates(cleanup_marker):
    center=create_cost_center(name=f"Centro {cleanup_marker}",code=f"CC-{cleanup_marker}",created_by=cleanup_marker.lower())
    edited=update_cost_center(center.id,name=f"Centro Editado {cleanup_marker}",code=f"CC-{cleanup_marker}",status="ativo")
    assert "Editado" in edited.name
    percent=create_allocation_rule(cost_center_id=center.id,name="Percentual",category="taxa",item=None,allocation_method="percentual",percentage=10,fixed_value=None,valid_from=date(2026,1,1),valid_until=None,status="ativo",created_by=cleanup_marker.lower(),notes=None)
    fixed=create_allocation_rule(cost_center_id=center.id,name="Fixo",category="taxa",item="Sala",allocation_method="valor_fixo",percentage=None,fixed_value=5,valid_from=date(2026,1,1),valid_until=None,status="ativo",created_by=cleanup_marker.lower(),notes=None)
    db=SessionLocal()
    try:
        batch=ProductionImportBatch(batch_name=f"Rateio {cleanup_marker}",source_type="manual",source_system="planilha",import_status="processado");db.add(batch);db.flush();record=ProductionRecord(batch_id=batch.id,service_date=date(2026,7,1),category="taxa",item="Sala",quantity=2,paid_value=100,cost_value=80,source_row_number=2,validation_status="valido");db.add(record);db.commit()
        result=estimate_indirect_cost_for_record(db,record);assert result["estimated_indirect_cost"]==Decimal("13.00") and len(result["rules"])==2
        record.category="outra";db.commit();assert estimate_indirect_cost_for_record(db,record)["status"]=="sem_regra"
    finally:db.close()

def test_negative_rules_are_rejected(cleanup_marker):
    center=create_cost_center(name=f"Negativo {cleanup_marker}",code=f"NEG-{cleanup_marker}")
    base=dict(cost_center_id=center.id,name="R",category=None,item=None,valid_from=date(2026,1,1),valid_until=None,status="ativo",created_by=None,notes=None)
    with pytest.raises(ValueError,match="negativo"):create_allocation_rule(**base,allocation_method="percentual",percentage=-1,fixed_value=None)
    with pytest.raises(ValueError,match="negativo"):create_allocation_rule(**base,allocation_method="valor_fixo",percentage=None,fixed_value=-1)

@pytest.mark.integration
def test_cost_routes_permissions_audit(admin_client,readonly_client,cleanup_marker,admin_username):
    response=admin_client.post("/cost-centers",data={"name":f"Rota {cleanup_marker}","code":f"R-{cleanup_marker}","status":"ativo"},follow_redirects=False);assert response.status_code==303
    center_id=int(response.headers["location"].split("/")[-1]);assert admin_client.post(f"/cost-centers/{center_id}/edit",data={"name":f"Rota Editada {cleanup_marker}","code":f"R-{cleanup_marker}","status":"ativo"},follow_redirects=False).status_code==303
    assert readonly_client.get("/cost-centers").status_code==200 and readonly_client.get("/cost-centers/new",follow_redirects=False).status_code==403
    db=SessionLocal()
    try:actions={row.action for row in db.query(AuditLog).filter(AuditLog.username==admin_username).all()};assert {"cost_center_created","cost_center_updated"}<=actions
    finally:db.close()

def test_cost_routes_protected():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        for path in ("/cost-centers","/cost-allocation-rules"):
            assert client.get(path,follow_redirects=False).status_code==303
