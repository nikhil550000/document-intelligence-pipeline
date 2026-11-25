# pdfium-deepseek-flash on smoke

- Run `01a20484-dd6b-7df9-9055-f0ac4705b4fd` of configuration `pdfium-deepseek-flash` on the `smoke` list, at commit `f6c0a68e34d5604b72715cf9237e339ae76e5b49`.
- Model `accounts/fireworks/models/deepseek-v4p1-flash-1017`, prompt version 1, parser `pdfium`.
- Started 2026-11-22 18:29 UTC, ceiling $0.000000.
- Contracts answered: **5 of 5** (5 valid). A contract without a record counts as null on every field, so what CUAD has in it is missed.
- Cost at list price: $0.0310, $6.20 per 1,000 contracts. Spent in this run: $0.0000; the rest came from the cache.
- Seconds per contract: mean 0.1, median 0.0, 95th percentile 0.1.

Scores are percentages, each with its 95% interval.

## Overall

|  | Precision | Recall | F1 |
|---|---|---|---|
| Micro (counts of all fields added) | 77.6 (67.9 to 85.2) | 88.1 (82.6 to 94.6) | 82.5 (75.2 to 89.1) |
| Macro (mean of the 41 fields) | 75.3 (69.5 to 85.0) | 86.3 (79.5 to 93.5) | 72.1 (64.0 to 79.6) |

## By field type

| Field type | Support | Precision | Recall | F1 |
|---|---|---|---|---|
| text | 5 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| entity_list | 13 | 84.6 (69.2 to 100.0) | 84.6 (69.2 to 100.0) | 84.6 (69.2 to 100.0) |
| date | 12 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| duration | 2 | 66.7 (50.0 to 100.0) | 100.0 (100.0 to 100.0) | 80.0 (66.7 to 100.0) |
| jurisdiction | 4 | 75.0 (25.0 to 100.0) | 75.0 (25.0 to 100.0) | 75.0 (25.0 to 100.0) |
| clause | 31 | 66.7 (59.5 to 78.4) | 83.9 (69.7 to 96.3) | 74.3 (65.6 to 82.2) |

## By field

Support is the number of CUAD answers: contracts, or party names. Under 10 it is marked low, and the score is not to be read alone.

| Field | Support | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| `document_name` | 5 (low) | 5 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `parties` | 13 | 11 | 2 | 2 | 84.6 (69.2 to 100.0) | 84.6 (69.2 to 100.0) | 84.6 (69.2 to 100.0) |
| `agreement_date` | 4 (low) | 4 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `effective_date` | 5 (low) | 5 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `expiration_date` | 3 (low) | 3 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `renewal_term` | 2 (low) | 2 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `notice_to_terminate_renewal` | 0 (low) | 0 | 1 | 0 | 0.0 (0.0 to 0.0) | - | 0.0 (0.0 to 0.0) |
| `governing_law` | 4 (low) | 3 | 1 | 1 | 75.0 (25.0 to 100.0) | 75.0 (25.0 to 100.0) | 75.0 (25.0 to 100.0) |
| `most_favored_nation` | 0 (low) | 0 | 0 | 0 | - | - | - |
| `competitive_restriction_exception` | 2 (low) | 2 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `non_compete` | 1 (low) | 1 | 2 | 0 | 33.3 (0.0 to 100.0) | 100.0 (100.0 to 100.0) | 50.0 (0.0 to 100.0) |
| `exclusivity` | 3 (low) | 3 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `no_solicit_of_customers` | 1 (low) | 1 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `no_solicit_of_employees` | 1 (low) | 1 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `non_disparagement` | 1 (low) | 1 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `termination_for_convenience` | 1 (low) | 1 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `right_of_first_refusal_offer_or_negotiation` | 0 (low) | 0 | 0 | 0 | - | - | - |
| `change_of_control` | 0 (low) | 0 | 0 | 0 | - | - | - |
| `anti_assignment` | 1 (low) | 1 | 1 | 0 | 50.0 (0.0 to 100.0) | 100.0 (100.0 to 100.0) | 66.7 (0.0 to 100.0) |
| `revenue_or_profit_sharing` | 5 (low) | 4 | 0 | 1 | 100.0 (100.0 to 100.0) | 80.0 (40.0 to 100.0) | 88.9 (57.1 to 100.0) |
| `price_restrictions` | 0 (low) | 0 | 1 | 0 | 0.0 (0.0 to 0.0) | - | 0.0 (0.0 to 0.0) |
| `minimum_commitment` | 2 (low) | 2 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `volume_restriction` | 1 (low) | 0 | 1 | 1 | 0.0 (0.0 to 0.0) | 0.0 (0.0 to 0.0) | 0.0 (0.0 to 0.0) |
| `ip_ownership_assignment` | 0 (low) | 0 | 0 | 0 | - | - | - |
| `joint_ip_ownership` | 0 (low) | 0 | 0 | 0 | - | - | - |
| `license_grant` | 2 (low) | 2 | 1 | 0 | 66.7 (0.0 to 100.0) | 100.0 (100.0 to 100.0) | 80.0 (0.0 to 100.0) |
| `non_transferable_license` | 1 (low) | 1 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `affiliate_license_licensor` | 0 (low) | 0 | 0 | 0 | - | - | - |
| `affiliate_license_licensee` | 0 (low) | 0 | 0 | 0 | - | - | - |
| `unlimited_license` | 0 (low) | 0 | 0 | 0 | - | - | - |
| `irrevocable_or_perpetual_license` | 0 (low) | 0 | 0 | 0 | - | - | - |
| `source_code_escrow` | 0 (low) | 0 | 0 | 0 | - | - | - |
| `post_termination_services` | 0 (low) | 0 | 5 | 0 | 0.0 (0.0 to 0.0) | - | 0.0 (0.0 to 0.0) |
| `audit_rights` | 2 (low) | 2 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `uncapped_liability` | 0 (low) | 0 | 2 | 0 | 0.0 (0.0 to 0.0) | - | 0.0 (0.0 to 0.0) |
| `cap_on_liability` | 3 (low) | 2 | 0 | 1 | 100.0 (100.0 to 100.0) | 66.7 (0.0 to 100.0) | 80.0 (0.0 to 100.0) |
| `liquidated_damages` | 1 (low) | 1 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `warranty_duration` | 0 (low) | 0 | 0 | 0 | - | - | - |
| `insurance` | 1 (low) | 0 | 0 | 1 | - | 0.0 (0.0 to 0.0) | 0.0 (0.0 to 0.0) |
| `covenant_not_to_sue` | 2 (low) | 1 | 0 | 1 | 100.0 (100.0 to 100.0) | 50.0 (0.0 to 100.0) | 66.7 (0.0 to 100.0) |
| `third_party_beneficiary` | 0 (low) | 0 | 0 | 0 | - | - | - |

## Cases skipped, by rule

| Field | Rule | Contracts |
|---|---|---|
| `agreement_date` | redacted | 1 |
| `renewal_term` | passage only | 1 |

## Contracts without a record

None.
