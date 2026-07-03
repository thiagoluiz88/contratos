from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, Text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class AccessProfile(Base):
    __tablename__ = "access_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="access_profile")


class Operator(Base):
    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    ans_registration: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contracts: Mapped[list["Contract"]] = relationship(back_populates="operator")


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), default="manual")
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_filepath: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    imported_records: Mapped[int] = mapped_column(Integer, default=0)
    failed_records: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    records: Mapped[list["ImportedContractRecord"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    contract_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    operator_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    responsible_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adjustment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contract_object: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    auto_renewal: Mapped[bool] = mapped_column(Boolean, default=False)
    renewal_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    termination_notice_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    payment_term_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_trigger: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_interest_clause: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_penalty_clause: Mapped[bool] = mapped_column(Boolean, default=False)

    billing_deadline_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    billing_deadline_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    allows_glosa_unilateral: Mapped[bool] = mapped_column(Boolean, default=False)
    glosa_deadline_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    glosa_appeal_deadline_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    glosa_response_deadline_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    glosa_clause_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    reajust_clause_exists: Mapped[bool] = mapped_column(Boolean, default=False)
    reajust_frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reajust_index: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reajust_percentage: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    base_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reajust_clause_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)

    medical_fee_table: Mapped[str | None] = mapped_column(String(255), nullable=True)
    medical_fee_table_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    daily_rate_table: Mapped[str | None] = mapped_column(String(255), nullable=True)
    materials_table: Mapped[str | None] = mapped_column(String(255), nullable=True)
    materials_table_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    medicines_table: Mapped[str | None] = mapped_column(String(255), nullable=True)
    medicines_table_version: Mapped[str | None] = mapped_column(String(100), nullable=True)

    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_total: Mapped[float] = mapped_column(Float, default=0)
    classification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    strong_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    weak_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    alerts: Mapped[str | None] = mapped_column(Text, nullable=True)

    extraction_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_filepath: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    operator: Mapped[Operator | None] = relationship(back_populates="contracts")
    parent_contract: Mapped["Contract | None"] = relationship(remote_side=[id], back_populates="child_contracts")
    child_contracts: Mapped[list["Contract"]] = relationship(back_populates="parent_contract")
    files: Mapped[list["ContractFile"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    extractions: Mapped[list["ContractExtraction"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    additives: Mapped[list["ContractAdditive"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    analyses: Mapped[list["AIAnalysis"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    clauses: Mapped[list["ContractClause"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    events: Mapped[list["ContractEvent"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    adjustments: Mapped[list["ContractAdjustment"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    remuneration_tables: Mapped[list["RemunerationTable"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    materials_medicines_rules: Mapped[list["MaterialsMedicinesRule"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    terms: Mapped[list["ContractTerm"]] = relationship(back_populates="contract", cascade="all, delete-orphan")


class ContractAdjustment(Base):
    __tablename__ = "contract_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    reference_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    adjustment_index: Mapped[str | None] = mapped_column(String(100), nullable=True)
    applied_percentage: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    requested_percentage: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    adjustment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    request_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    approval_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_file_id: Mapped[int | None] = mapped_column(ForeignKey("contract_files.id", ondelete="SET NULL"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="adjustments")
    document_file: Mapped["ContractFile | None"] = relationship()


class ContractTerm(Base):
    __tablename__ = "contract_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    deadline_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("contract_files.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="terms")
    source_document: Mapped["ContractFile | None"] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RemunerationTable(Base):
    __tablename__ = "remuneration_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    table_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reference_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="remuneration_tables")
    items: Mapped[list["RemunerationTableItem"]] = relationship(back_populates="remuneration_table", cascade="all, delete-orphan")


class RemunerationTableItem(Base):
    __tablename__ = "remuneration_table_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    remuneration_table_id: Mapped[int] = mapped_column(ForeignKey("remuneration_tables.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    proposed_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    adjustment_percentage: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    billing_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    remuneration_table: Mapped[RemunerationTable] = relationship(back_populates="items")


class MaterialsMedicinesRule(Base):
    __tablename__ = "materials_medicines_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    billing_reference: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    addition_percentage: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    reduction_percentage: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    rule_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="materials_medicines_rules")


class ContractEvent(Base):
    __tablename__ = "contract_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(50), default="nota")
    title: Mapped[str] = mapped_column(String(255))
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="events")


class AuthAuditEvent(Base):
    __tablename__ = "auth_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped["User | None"] = relationship(back_populates="auth_audit_events")


class ImportedContractRecord(Base):
    __tablename__ = "imported_contract_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    normalized_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    batch: Mapped[ImportBatch] = relationship(back_populates="records")


class ContractFile(Base):
    __tablename__ = "contract_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    file_type: Mapped[str] = mapped_column(String(50), default="contract")
    document_type: Mapped[str] = mapped_column(String(50), default="contrato", index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filepath: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    extraction_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(50), default="pendente", index=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="files")
    extractions: Mapped[list["ContractExtraction"]] = relationship(back_populates="contract_file", cascade="all, delete-orphan")


class ContractExtraction(Base):
    __tablename__ = "contract_extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_file_id: Mapped[int] = mapped_column(ForeignKey("contract_files.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    extraction_status: Mapped[str] = mapped_column(String(50), default="pendente", nullable=False, index=True)
    extracted_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    extraction_warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    character_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_status: Mapped[str] = mapped_column(String(50), default="pendente", nullable=False, index=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contract_file: Mapped[ContractFile] = relationship(back_populates="extractions")
    contract: Mapped[Contract] = relationship(back_populates="extractions")


class ContractAdditive(Base):
    __tablename__ = "contract_additives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    additive_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    additive_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    object_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    reajust_index: Mapped[str | None] = mapped_column(String(100), nullable=True)
    responsible_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    responsible_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_filepath: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="additives")


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("contract_files.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="completed", index=True)
    score_total: Mapped[float] = mapped_column(Float, default=0)
    score_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_legal_security: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_clarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_financial_protection: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_compliance: Mapped[float | None] = mapped_column(Float, nullable=True)
    failures_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_clauses_count: Mapped[int] = mapped_column(Integer, default=0)
    opportunities_count: Mapped[int] = mapped_column(Integer, default=0)
    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="analyses")
    issues: Mapped[list["ContractIssue"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    opportunities: Mapped[list["NegotiationOpportunity"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class ContractClause(Base):
    __tablename__ = "contract_clauses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("ai_analyses.id", ondelete="SET NULL"), nullable=True, index=True)
    clause_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    impact_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contract: Mapped[Contract] = relationship(back_populates="clauses")


class ContractIssue(Base):
    __tablename__ = "contract_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("ai_analyses.id", ondelete="CASCADE"), index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    clause_id: Mapped[int | None] = mapped_column(ForeignKey("contract_clauses.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(String(50), default="medium", index=True)
    impact_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    analysis: Mapped[AIAnalysis] = relationship(back_populates="issues")


class NegotiationOpportunity(Base):
    __tablename__ = "negotiation_opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("ai_analyses.id", ondelete="CASCADE"), index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(50), default="medium", index=True)
    potential_impact: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    analysis: Mapped[AIAnalysis] = relationship(back_populates="opportunities")
    messages: Mapped[list["NegotiationMessage"]] = relationship(back_populates="negotiation_opportunity", cascade="all, delete-orphan")


class NegotiationMessage(Base):
    __tablename__ = "negotiation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    negotiation_opportunity_id: Mapped[int] = mapped_column(ForeignKey("negotiation_opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    message_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    channel: Mapped[str] = mapped_column(String(50), default="other", index=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    contract_file_id: Mapped[int | None] = mapped_column(ForeignKey("contract_files.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    negotiation_opportunity: Mapped[NegotiationOpportunity] = relationship(back_populates="messages")
    user: Mapped["User | None"] = relationship(back_populates="negotiation_messages")
    contract_file: Mapped["ContractFile | None"] = relationship()


class ContractComparison(Base):
    __tablename__ = "contract_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", index=True)
    criteria_count: Mapped[int] = mapped_column(Integer, default=0)
    best_contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list["ContractComparisonItem"]] = relationship(back_populates="comparison", cascade="all, delete-orphan")


class ContractComparisonItem(Base):
    __tablename__ = "contract_comparison_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    comparison_id: Mapped[int] = mapped_column(ForeignKey("contract_comparisons.id", ondelete="CASCADE"), index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=1)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    comparison: Mapped[ContractComparison] = relationship(back_populates="items")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    access_profile_id: Mapped[int | None] = mapped_column(ForeignKey("access_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    access_profile: Mapped[AccessProfile | None] = relationship(back_populates="users")
    negotiation_messages: Mapped[list[NegotiationMessage]] = relationship(back_populates="user")
    auth_audit_events: Mapped[list[AuthAuditEvent]] = relationship(back_populates="user")
