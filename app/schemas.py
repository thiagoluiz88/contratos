from datetime import date, datetime
from pydantic import BaseModel


class ContractBase(BaseModel):
    contract_name: str
    operator_name: str | None = None
    contract_number: str | None = None
    contract_object: str | None = None
    signature_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    auto_renewal: bool = False
    renewal_details: str | None = None
    termination_notice_days: int | None = None
    payment_term_days: int | None = None
    payment_trigger: str | None = None
    payment_interest_clause: bool = False
    payment_penalty_clause: bool = False
    billing_deadline_days: int | None = None
    billing_deadline_description: str | None = None
    allows_glosa_unilateral: bool = False
    glosa_deadline_days: int | None = None
    glosa_appeal_deadline_days: int | None = None
    glosa_response_deadline_days: int | None = None
    glosa_clause_summary: str | None = None
    reajust_clause_exists: bool = False
    reajust_frequency: str | None = None
    reajust_index: str | None = None
    reajust_clause_summary: str | None = None
    medical_fee_table: str | None = None
    medical_fee_table_version: str | None = None
    daily_rate_table: str | None = None
    materials_table: str | None = None
    materials_table_version: str | None = None
    medicines_table: str | None = None
    medicines_table_version: str | None = None
    raw_text: str | None = None
    score_total: float = 0
    classification: str | None = None
    risk_level: str | None = None
    strong_points: str | None = None
    weak_points: str | None = None
    alerts: str | None = None
    original_filename: str | None = None
    stored_filepath: str | None = None


class ContractCreate(ContractBase):
    pass


class ContractRead(ContractBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserRegister(BaseModel):
    username: str
    email: str
    password: str
    password_confirm: str
    full_name: str | None = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
