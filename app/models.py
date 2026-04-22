from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, Text, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_name: Mapped[str] = mapped_column(String(255), nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
    reajust_clause_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

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


class ContractEvent(Base):
    __tablename__ = "contract_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(50), default="nota")
    title: Mapped[str] = mapped_column(String(255))
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
