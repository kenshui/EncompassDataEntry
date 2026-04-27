from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ProcessingStatus(str, Enum):
    NEW = "new"
    PROCESSED = "processed"
    FAILED = "failed"


@dataclass(frozen=True)
class Token:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None


@dataclass(frozen=True)
class LoanSummary:
    loan_id: str
    created_at: datetime | None = None
    modified_at: datetime | None = None


@dataclass(frozen=True)
class AttachmentMetadata:
    loan_id: str
    attachment_id: str
    title: str
    created_at: datetime | None
    created_by: str | None


@dataclass(frozen=True)
class AttachmentRecord:
    loan_id: str
    attachment_id: str
    title: str
    created_at: datetime | None
    created_by: str | None


@dataclass(frozen=True)
class FieldDefinition:
    key: str
    label: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProcessingEvent:
    status: str
    message: str
    loan_id: str | None = None
    attachment_id: str | None = None
    fields: dict[str, Any] | None = None


@dataclass
class AgentRunSummary:
    loans_scanned: int = 0
    attachments_seen: int = 0
    attachments_skipped: int = 0
    attachments_processed: int = 0
    field_updates_succeeded: int = 0
    field_updates_failed: int = 0


@dataclass(frozen=True)
class ExtractedFields:
    loan_id: str
    attachment_id: str
    values: dict[str, Any]


FIELD_DEFINITIONS: tuple[FieldDefinition, ...] = (
    FieldDefinition("owner_title_insurance_fees", "Owner's Title Insurance Fees", ("Owner Title Insurance",)),
    FieldDefinition("lenders_title_insurance_fees", "Lenders' Title Insurance Fees", ("Lender's Title Insurance",)),
    FieldDefinition("recording_fees", "Recording Fees", ("Recording Fee",)),
    FieldDefinition("transfer_taxes", "Transfer Taxes", ("Transfer Tax",)),
    FieldDefinition("transfer_tax_city", "Transfer Tax City", ("City Transfer Tax",)),
    FieldDefinition("processing_fee", "Processing Fee"),
    FieldDefinition("underwriting_fee", "Underwriting Fee"),
    FieldDefinition("voe_fee", "VOE fee", ("Verification of Employment Fee", "VOE")),
    FieldDefinition("appraisal_fee", "Appraisal Fee"),
    FieldDefinition("credit_report_fee", "Credit Report Fee"),
    FieldDefinition("flood_certification", "Flood Certification", ("Flood Certification Fee",)),
    FieldDefinition("mortgage_insurance_premium", "Mortgage Insurance Premium", ("MI Premium",)),
    FieldDefinition("tax_service_fee", "Tax Service Fee"),
    FieldDefinition("homeowners_insurance_premium", "Homeowner's Insurance Premium", ("Homeowners Insurance Premium",)),
    FieldDefinition("prepaid_interest_amount", "Prepaid Interest Amount"),
    FieldDefinition("prepaid_interest_rate", "Prepaid Interest Rate"),
    FieldDefinition("homeowners_insurance_monthly_cost", "Homeowner's Insurance monthly cost", ("Homeowners Insurance Monthly Cost",)),
    FieldDefinition("mortgage_insurance_cost", "Mortgage Insurance Cost", ("Monthly Mortgage Insurance",)),
    FieldDefinition("property_taxes", "Property Taxes", ("Property Tax",)),
    FieldDefinition("title_courier_fee", "Title-Courier Fee", ("Title Courier Fee",)),
    FieldDefinition("title_escrow_fee", "Title- Escrow Fee", ("Title Escrow Fee",)),
    FieldDefinition("title_lenders_title_insurance_fee", "Title- Lender's Title Insurance Fee", ("Title Lenders Title Insurance Fee",)),
    FieldDefinition("title_loan_tie_in_fee", "Title - Loan Tie In fee", ("Title Loan Tie In Fee",)),
    FieldDefinition("title_recording_service_fee", "Title - Recording Service Fee", ("Title Recording Service Fee",)),
    FieldDefinition("title_title_endorsement_fees", "Title - Title Endorsement Fees", ("Title Endorsement Fees",)),
    FieldDefinition("sales_contract_price", "Sales Contract Price", ("Purchase Price", "Contract Price")),
    FieldDefinition("loan_amount", "Loan Amount", ("Base Loan Amount",)),
)
