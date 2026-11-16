"""Read CUAD's labelled passages and written answers from master_clauses.csv."""

import csv
from dataclasses import dataclass
from pathlib import Path

from docintel.evaluation.dataset import CUAD_FOLDER_NAME

MASTER_CLAUSES_PATH = Path("data") / CUAD_FOLDER_NAME / "CUAD_v1" / "master_clauses.csv"

# Our field name -> the name of CUAD's passage column. The answer column is
# found from it by `answer_column_name`.
CUAD_COLUMN_NAMES = {
    "document_name": "Document Name",
    "parties": "Parties",
    "agreement_date": "Agreement Date",
    "effective_date": "Effective Date",
    "expiration_date": "Expiration Date",
    "renewal_term": "Renewal Term",
    "notice_to_terminate_renewal": "Notice Period To Terminate Renewal",
    "governing_law": "Governing Law",
    "most_favored_nation": "Most Favored Nation",
    "competitive_restriction_exception": "Competitive Restriction Exception",
    "non_compete": "Non-Compete",
    "exclusivity": "Exclusivity",
    "no_solicit_of_customers": "No-Solicit Of Customers",
    "no_solicit_of_employees": "No-Solicit Of Employees",
    "non_disparagement": "Non-Disparagement",
    "termination_for_convenience": "Termination For Convenience",
    "right_of_first_refusal_offer_or_negotiation": "Rofr/Rofo/Rofn",
    "change_of_control": "Change Of Control",
    "anti_assignment": "Anti-Assignment",
    "revenue_or_profit_sharing": "Revenue/Profit Sharing",
    "price_restrictions": "Price Restrictions",
    "minimum_commitment": "Minimum Commitment",
    "volume_restriction": "Volume Restriction",
    "ip_ownership_assignment": "Ip Ownership Assignment",
    "joint_ip_ownership": "Joint Ip Ownership",
    "license_grant": "License Grant",
    "non_transferable_license": "Non-Transferable License",
    "affiliate_license_licensor": "Affiliate License-Licensor",
    "affiliate_license_licensee": "Affiliate License-Licensee",
    "unlimited_license": "Unlimited/All-You-Can-Eat-License",
    "irrevocable_or_perpetual_license": "Irrevocable Or Perpetual License",
    "source_code_escrow": "Source Code Escrow",
    "post_termination_services": "Post-Termination Services",
    "audit_rights": "Audit Rights",
    "uncapped_liability": "Uncapped Liability",
    "cap_on_liability": "Cap On Liability",
    "liquidated_damages": "Liquidated Damages",
    "warranty_duration": "Warranty Duration",
    "insurance": "Insurance",
    "covenant_not_to_sue": "Covenant Not To Sue",
    "third_party_beneficiary": "Third Party Beneficiary",
}


@dataclass(frozen=True)
class CuadAnswer:
    """What CUAD has for one field of one contract, exactly as written in the file.

    An empty passage is "[]" and an empty answer is "" or "[]". Neither is
    interpreted here.
    """

    passage: str
    answer: str


def answer_column_name(passage_column_name: str) -> str:
    """Returns the name of the answer column that goes with a passage column."""
    if passage_column_name == "Notice Period To Terminate Renewal":
        # CUAD's header for this one column has a stray space.
        return passage_column_name + "- Answer"
    return passage_column_name + "-Answer"


def load_cuad_answers(path: Path) -> dict[str, dict[str, CuadAnswer]]:
    """Reads master_clauses.csv.

    Returns:
        For each contract file name, the CUAD passage and answer for each of our
        field names.
    """
    answers_by_contract: dict[str, dict[str, CuadAnswer]] = {}
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            answers_by_field = {}
            for field_name, passage_column_name in CUAD_COLUMN_NAMES.items():
                answers_by_field[field_name] = CuadAnswer(
                    passage=row[passage_column_name],
                    answer=row[answer_column_name(passage_column_name)],
                )
            answers_by_contract[row["Filename"]] = answers_by_field
    return answers_by_contract
