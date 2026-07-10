from __future__ import annotations
from decimal import Decimal
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import CostAllocationRule, CostCenter, ProductionRecord
from app.services.contract_terms_comparison_service import fold_text

METHODS = {"percentual", "valor_fixo", "por_quantidade", "manual_futuro"}

def list_cost_centers(db: Session): return db.query(CostCenter).order_by(CostCenter.name).all()
def list_allocation_rules(db: Session, cost_center_id=None):
    query = db.query(CostAllocationRule)
    if cost_center_id: query = query.filter(CostAllocationRule.cost_center_id == cost_center_id)
    return query.order_by(CostAllocationRule.name).all()

def _validate_rule(values):
    method = values.get("allocation_method"); percentage = values.get("percentage"); fixed = values.get("fixed_value")
    if method not in METHODS: raise ValueError("Método de rateio inválido.")
    if not values.get("cost_center_id"): raise ValueError("Centro de custo é obrigatório.")
    if not values.get("valid_from"): raise ValueError("Vigência inicial é obrigatória.")
    if method == "percentual" and percentage is None: raise ValueError("Percentual é obrigatório.")
    if percentage is not None and Decimal(str(percentage)) < 0: raise ValueError("Percentual não pode ser negativo.")
    if method in {"valor_fixo", "por_quantidade"} and fixed is None: raise ValueError("Valor fixo é obrigatório.")
    if fixed is not None and Decimal(str(fixed)) < 0: raise ValueError("Valor fixo não pode ser negativo.")
    if values.get("valid_until") and values["valid_until"] < values["valid_from"]: raise ValueError("Vigência final anterior à inicial.")

def create_cost_center(*, name, code, status="ativo", notes=None, created_by=None):
    db=SessionLocal()
    try:
        if not str(name).strip() or not str(code).strip(): raise ValueError("Nome e código são obrigatórios.")
        center=CostCenter(name=str(name).strip(),code=str(code).strip(),status=status,notes=notes,created_by=created_by);db.add(center);db.commit();db.refresh(center);return center
    except Exception: db.rollback();raise
    finally: db.close()
def update_cost_center(center_id, **values):
    db=SessionLocal()
    try:
        center=db.get(CostCenter,center_id)
        if not center: raise ValueError("Centro de custo não encontrado.")
        for field in ("name","code","status","notes"):
            if field in values: setattr(center,field,values[field])
        if not center.name.strip() or not center.code.strip(): raise ValueError("Nome e código são obrigatórios.")
        db.commit();db.refresh(center);return center
    except Exception: db.rollback();raise
    finally: db.close()
def create_allocation_rule(**values):
    _validate_rule(values);db=SessionLocal()
    try:
        rule=CostAllocationRule(**values);db.add(rule);db.commit();db.refresh(rule);return rule
    except Exception: db.rollback();raise
    finally: db.close()
def update_allocation_rule(rule_id, **values):
    db=SessionLocal()
    try:
        rule=db.get(CostAllocationRule,rule_id)
        if not rule: raise ValueError("Regra não encontrada.")
        merged={field:getattr(rule,field) for field in ("cost_center_id","allocation_method","percentage","fixed_value","valid_from","valid_until")};merged.update(values);_validate_rule(merged)
        for field,value in values.items(): setattr(rule,field,value)
        db.commit();db.refresh(rule);return rule
    except Exception: db.rollback();raise
    finally: db.close()

def get_active_rules_for_record(db: Session, record: ProductionRecord):
    if not record.service_date: return []
    rules=db.query(CostAllocationRule).join(CostCenter).filter(CostAllocationRule.status=="ativo",CostCenter.status=="ativo",CostAllocationRule.valid_from<=record.service_date,or_(CostAllocationRule.valid_until.is_(None),CostAllocationRule.valid_until>=record.service_date)).all()
    return [rule for rule in rules if (not rule.category or fold_text(rule.category)==fold_text(record.category)) and (not rule.item or fold_text(rule.item)==fold_text(record.item))]

def estimate_indirect_cost_for_record(db: Session, record: ProductionRecord):
    rules=get_active_rules_for_record(db,record);details=[];total=Decimal("0");pending=[]
    if not rules: return {"status":"sem_regra","message":"Nenhuma regra ativa aplicável ao registro.","estimated_indirect_cost":None,"rules":[],"pending":["Regra de rateio não encontrada."]}
    for rule in rules:
        value=None;base=None
        if rule.allocation_method=="percentual":
            base=record.cost_value if record.cost_value is not None else record.paid_value
            if base is None: pending.append(f"Base ausente para regra {rule.name}.")
            else: value=Decimal(str(base))*Decimal(str(rule.percentage))/Decimal("100")
        elif rule.allocation_method=="valor_fixo": value=Decimal(str(rule.fixed_value))
        elif rule.allocation_method=="por_quantidade":
            if record.quantity is None: pending.append(f"Quantidade ausente para regra {rule.name}.")
            else: value=Decimal(str(record.quantity))*Decimal(str(rule.fixed_value))
        else: pending.append(f"Regra {rule.name} requer alocação manual futura.")
        if value is not None: value=value.quantize(Decimal("0.01"));total+=value
        details.append({"rule":rule,"base":base,"estimated_value":value})
    return {"status":"ok" if details and not pending else "pendente","message":"Estimativa preliminar de custo indireto; não representa margem final.","estimated_indirect_cost":total.quantize(Decimal("0.01")) if any(row["estimated_value"] is not None for row in details) else None,"rules":details,"pending":pending}

def build_cost_allocation_summary(db: Session, records):
    results=[{"record":record,"estimate":estimate_indirect_cost_for_record(db,record)} for record in records]
    values=[row["estimate"]["estimated_indirect_cost"] for row in results if row["estimate"]["estimated_indirect_cost"] is not None]
    return {"records":results,"estimated_indirect_cost":sum(values,Decimal("0")).quantize(Decimal("0.01")) if values else None,"pending_records":sum(row["estimate"]["status"]!="ok" for row in results)}
