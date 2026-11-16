"""The 41 fields extracted from every contract, and the type of each answer."""

from dataclasses import dataclass
from enum import Enum


class FieldType(Enum):
    """The kind of answer a field holds."""

    TEXT = "text"
    ENTITY_LIST = "entity_list"
    DATE = "date"
    DURATION = "duration"
    JURISDICTION = "jurisdiction"
    CLAUSE = "clause"


@dataclass(frozen=True)
class Field:
    """One contract field: its name in our records and the type of its answer."""

    name: str
    type: FieldType


NON_CLAUSE_FIELDS = (
    Field("document_name", FieldType.TEXT),
    Field("parties", FieldType.ENTITY_LIST),
    Field("agreement_date", FieldType.DATE),
    Field("effective_date", FieldType.DATE),
    Field("expiration_date", FieldType.DATE),
    Field("renewal_term", FieldType.DURATION),
    Field("notice_to_terminate_renewal", FieldType.DURATION),
    Field("governing_law", FieldType.JURISDICTION),
)

CLAUSE_FIELD_NAMES = (
    "most_favored_nation",
    "competitive_restriction_exception",
    "non_compete",
    "exclusivity",
    "no_solicit_of_customers",
    "no_solicit_of_employees",
    "non_disparagement",
    "termination_for_convenience",
    "right_of_first_refusal_offer_or_negotiation",
    "change_of_control",
    "anti_assignment",
    "revenue_or_profit_sharing",
    "price_restrictions",
    "minimum_commitment",
    "volume_restriction",
    "ip_ownership_assignment",
    "joint_ip_ownership",
    "license_grant",
    "non_transferable_license",
    "affiliate_license_licensor",
    "affiliate_license_licensee",
    "unlimited_license",
    "irrevocable_or_perpetual_license",
    "source_code_escrow",
    "post_termination_services",
    "audit_rights",
    "uncapped_liability",
    "cap_on_liability",
    "liquidated_damages",
    "warranty_duration",
    "insurance",
    "covenant_not_to_sue",
    "third_party_beneficiary",
)

CLAUSE_FIELDS = tuple(Field(name, FieldType.CLAUSE) for name in CLAUSE_FIELD_NAMES)

ALL_FIELDS = NON_CLAUSE_FIELDS + CLAUSE_FIELDS
