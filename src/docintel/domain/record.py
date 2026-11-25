"""The record extracted from one contract: an answer and its quotes for each field."""

from datetime import date

from pydantic import BaseModel, ConfigDict

from docintel.domain.values import Duration, Perpetual

# Raised whenever a field is added, removed or changes its shape, so that a
# stored record says which shape it has.
SCHEMA_VERSION = "1"


class RecordPart(BaseModel):
    """Refuses unknown keys, and values of the wrong type instead of converting them."""

    # Without strict, "yes" would be read as true and "30" as the number 30.
    model_config = ConfigDict(extra="forbid", strict=True)


class Quote(RecordPart):
    """A passage copied word for word from the contract."""

    # The page is not asked of the model: the grounding check finds the quote in
    # the text page by page, and adds it then.
    text: str


# In every answer the quotes come first, so the model writes the passage before
# the answer it supports.


class TextAnswer(RecordPart):
    """A name written in the contract, or null when it gives none."""

    evidence: list[Quote]
    value: str | None


class PartiesAnswer(RecordPart):
    """The names of the parties who signed the contract."""

    evidence: list[Quote]
    names: list[str]


class DateAnswer(RecordPart):
    """A whole date, or null when the contract gives none."""

    evidence: list[Quote]
    value: date | None


class ExpirationDateAnswer(RecordPart):
    """The end of the initial term: a date, perpetual, or null."""

    evidence: list[Quote]
    value: date | Perpetual | None


class DurationAnswer(RecordPart):
    """A length of time, or null when the contract gives none."""

    evidence: list[Quote]
    value: Duration | None


class ClauseAnswer(RecordPart):
    """Whether the contract has a clause of this kind."""

    evidence: list[Quote]
    present: bool


class ContractRecord(RecordPart):
    """Every field of one contract. All are required, so none can be forgotten."""

    document_name: TextAnswer
    parties: PartiesAnswer
    agreement_date: DateAnswer
    effective_date: DateAnswer
    expiration_date: ExpirationDateAnswer
    renewal_term: DurationAnswer
    notice_to_terminate_renewal: DurationAnswer
    governing_law: TextAnswer
    most_favored_nation: ClauseAnswer
    competitive_restriction_exception: ClauseAnswer
    non_compete: ClauseAnswer
    exclusivity: ClauseAnswer
    no_solicit_of_customers: ClauseAnswer
    no_solicit_of_employees: ClauseAnswer
    non_disparagement: ClauseAnswer
    termination_for_convenience: ClauseAnswer
    right_of_first_refusal_offer_or_negotiation: ClauseAnswer
    change_of_control: ClauseAnswer
    anti_assignment: ClauseAnswer
    revenue_or_profit_sharing: ClauseAnswer
    price_restrictions: ClauseAnswer
    minimum_commitment: ClauseAnswer
    volume_restriction: ClauseAnswer
    ip_ownership_assignment: ClauseAnswer
    joint_ip_ownership: ClauseAnswer
    license_grant: ClauseAnswer
    non_transferable_license: ClauseAnswer
    affiliate_license_licensor: ClauseAnswer
    affiliate_license_licensee: ClauseAnswer
    unlimited_license: ClauseAnswer
    irrevocable_or_perpetual_license: ClauseAnswer
    source_code_escrow: ClauseAnswer
    post_termination_services: ClauseAnswer
    audit_rights: ClauseAnswer
    uncapped_liability: ClauseAnswer
    cap_on_liability: ClauseAnswer
    liquidated_damages: ClauseAnswer
    warranty_duration: ClauseAnswer
    insurance: ClauseAnswer
    covenant_not_to_sue: ClauseAnswer
    third_party_beneficiary: ClauseAnswer
