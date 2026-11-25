# pdfium-deepseek-flash on dev

- Run `01a204ae-4595-7bc4-8de4-17e369d351ee` of configuration `pdfium-deepseek-flash` on the `dev` list, at commit `362ae1e121625c65d6dce5db5a5cbcfe55f8c470`.
- Model `accounts/fireworks/models/deepseek-v4p1-flash-1017`, prompt version 1, parser `pdfium`.
- Started 2026-11-22 19:14 UTC, ceiling $3.00.
- Contracts answered: **96 of 96** (96 valid). A contract without a record counts as null on every field, so what CUAD has in it is missed.
- Cost at list price: $0.6208, $6.47 per 1,000 contracts. Spent in this run: $0.0028; the rest came from the cache.
- Seconds per contract: mean 0.2, median 0.1, 95th percentile 0.2.

Scores are percentages, each with its 95% interval.

## Overall

|  | Precision | Recall | F1 |
|---|---|---|---|
| Micro (counts of all fields added) | 80.5 (78.0 to 82.8) | 87.9 (85.4 to 90.1) | 84.0 (81.9 to 85.8) |
| Macro (mean of the 41 fields) | 77.1 (73.0 to 80.4) | 85.0 (80.4 to 89.3) | 78.3 (73.4 to 81.0) |

## By field type

| Field type | Support | Precision | Recall | F1 |
|---|---|---|---|---|
| text | 96 | 89.6 (83.3 to 94.8) | 89.6 (83.3 to 94.8) | 89.6 (83.3 to 94.8) |
| entity_list | 273 | 90.4 (84.8 to 94.3) | 89.7 (80.6 to 95.0) | 90.1 (83.2 to 94.3) |
| date | 184 | 90.9 (86.6 to 94.7) | 87.0 (82.4 to 91.3) | 88.9 (85.4 to 92.0) |
| duration | 47 | 85.5 (73.8 to 94.9) | 100.0 (100.0 to 100.0) | 92.2 (84.9 to 97.4) |
| jurisdiction | 85 | 96.4 (91.7 to 100.0) | 95.3 (90.5 to 98.9) | 95.9 (91.2 to 99.4) |
| clause | 659 | 71.6 (67.5 to 75.1) | 85.3 (82.1 to 88.0) | 77.8 (74.8 to 80.4) |

## By field

Support is the number of CUAD answers: contracts, or party names. Under 10 it is marked low, and the score is not to be read alone.

| Field | Support | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| `document_name` | 96 | 86 | 10 | 10 | 89.6 (83.3 to 94.8) | 89.6 (83.3 to 94.8) | 89.6 (83.3 to 94.8) |
| `parties` | 273 | 245 | 26 | 28 | 90.4 (84.8 to 94.3) | 89.7 (80.6 to 95.0) | 90.1 (83.2 to 94.3) |
| `agreement_date` | 74 | 63 | 2 | 11 | 96.9 (92.2 to 100.0) | 85.1 (77.0 to 93.1) | 90.6 (85.0 to 95.7) |
| `effective_date` | 57 | 55 | 12 | 2 | 82.1 (72.1 to 91.2) | 96.5 (90.9 to 100.0) | 88.7 (82.2 to 94.0) |
| `expiration_date` | 53 | 42 | 2 | 11 | 95.5 (88.4 to 100.0) | 79.2 (69.0 to 89.4) | 86.6 (79.0 to 92.9) |
| `renewal_term` | 29 | 29 | 2 | 0 | 93.5 (83.3 to 100.0) | 100.0 (100.0 to 100.0) | 96.7 (90.9 to 100.0) |
| `notice_to_terminate_renewal` | 18 | 18 | 6 | 0 | 75.0 (56.2 to 91.3) | 100.0 (100.0 to 100.0) | 85.7 (72.0 to 95.5) |
| `governing_law` | 85 | 81 | 3 | 4 | 96.4 (91.7 to 100.0) | 95.3 (90.5 to 98.9) | 95.9 (91.2 to 99.4) |
| `most_favored_nation` | 4 (low) | 3 | 1 | 1 | 75.0 (0.0 to 100.0) | 75.0 (0.0 to 100.0) | 75.0 (0.0 to 100.0) |
| `competitive_restriction_exception` | 13 | 12 | 20 | 1 | 37.5 (21.4 to 54.8) | 92.3 (73.3 to 100.0) | 53.3 (33.3 to 70.0) |
| `non_compete` | 23 | 22 | 6 | 1 | 78.6 (60.7 to 92.3) | 95.7 (84.6 to 100.0) | 86.3 (73.2 to 95.0) |
| `exclusivity` | 32 | 29 | 6 | 3 | 82.9 (69.2 to 94.6) | 90.6 (79.3 to 100.0) | 86.6 (76.7 to 94.1) |
| `no_solicit_of_customers` | 8 (low) | 6 | 3 | 2 | 66.7 (33.3 to 100.0) | 75.0 (37.5 to 100.0) | 70.6 (36.4 to 90.9) |
| `no_solicit_of_employees` | 8 (low) | 8 | 2 | 0 | 80.0 (50.0 to 100.0) | 100.0 (100.0 to 100.0) | 88.9 (66.7 to 100.0) |
| `non_disparagement` | 3 (low) | 2 | 3 | 1 | 40.0 (0.0 to 100.0) | 66.7 (0.0 to 100.0) | 50.0 (0.0 to 88.9) |
| `termination_for_convenience` | 29 | 25 | 5 | 4 | 83.3 (69.0 to 96.0) | 86.2 (74.1 to 96.9) | 84.7 (73.7 to 93.8) |
| `right_of_first_refusal_offer_or_negotiation` | 12 | 11 | 1 | 1 | 91.7 (72.7 to 100.0) | 91.7 (75.0 to 100.0) | 91.7 (77.4 to 100.0) |
| `change_of_control` | 21 | 17 | 6 | 4 | 73.9 (55.6 to 90.9) | 81.0 (62.5 to 96.0) | 77.3 (61.5 to 89.7) |
| `anti_assignment` | 68 | 68 | 4 | 0 | 94.4 (88.6 to 98.7) | 100.0 (100.0 to 100.0) | 97.1 (94.0 to 99.3) |
| `revenue_or_profit_sharing` | 35 | 26 | 4 | 9 | 86.7 (73.7 to 97.0) | 74.3 (58.1 to 87.8) | 80.0 (66.7 to 89.6) |
| `price_restrictions` | 3 (low) | 3 | 21 | 0 | 12.5 (0.0 to 26.1) | 100.0 (100.0 to 100.0) | 22.2 (0.0 to 41.4) |
| `minimum_commitment` | 31 | 20 | 3 | 11 | 87.0 (70.8 to 100.0) | 64.5 (46.7 to 80.6) | 74.1 (59.1 to 85.3) |
| `volume_restriction` | 18 | 5 | 6 | 13 | 45.5 (14.3 to 76.9) | 27.8 (7.1 to 50.0) | 34.5 (9.5 to 55.2) |
| `ip_ownership_assignment` | 21 | 21 | 8 | 0 | 72.4 (56.5 to 88.6) | 100.0 (100.0 to 100.0) | 84.0 (72.2 to 93.9) |
| `joint_ip_ownership` | 8 (low) | 6 | 0 | 2 | 100.0 (100.0 to 100.0) | 75.0 (40.0 to 100.0) | 85.7 (57.1 to 100.0) |
| `license_grant` | 41 | 41 | 7 | 0 | 85.4 (75.0 to 95.2) | 100.0 (100.0 to 100.0) | 92.1 (85.7 to 97.6) |
| `non_transferable_license` | 24 | 23 | 9 | 1 | 71.9 (54.8 to 86.7) | 95.8 (84.6 to 100.0) | 82.1 (68.1 to 91.7) |
| `affiliate_license_licensor` | 3 (low) | 2 | 0 | 1 | 100.0 (100.0 to 100.0) | 66.7 (0.0 to 100.0) | 80.0 (0.0 to 100.0) |
| `affiliate_license_licensee` | 7 (low) | 7 | 2 | 0 | 77.8 (50.0 to 100.0) | 100.0 (100.0 to 100.0) | 87.5 (66.7 to 100.0) |
| `unlimited_license` | 3 (low) | 2 | 0 | 1 | 100.0 (100.0 to 100.0) | 66.7 (0.0 to 100.0) | 80.0 (0.0 to 100.0) |
| `irrevocable_or_perpetual_license` | 13 | 11 | 1 | 2 | 91.7 (71.4 to 100.0) | 84.6 (62.5 to 100.0) | 88.0 (70.6 to 100.0) |
| `source_code_escrow` | 3 (low) | 3 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `post_termination_services` | 35 | 35 | 47 | 0 | 42.7 (32.5 to 53.8) | 100.0 (100.0 to 100.0) | 59.8 (49.0 to 70.0) |
| `audit_rights` | 42 | 41 | 2 | 1 | 95.3 (87.5 to 100.0) | 97.6 (92.0 to 100.0) | 96.5 (91.9 to 100.0) |
| `uncapped_liability` | 12 | 10 | 31 | 2 | 24.4 (12.1 to 37.8) | 83.3 (60.0 to 100.0) | 37.7 (20.4 to 53.7) |
| `cap_on_liability` | 51 | 32 | 1 | 19 | 97.0 (89.5 to 100.0) | 62.7 (50.9 to 76.0) | 76.2 (65.9 to 85.4) |
| `liquidated_damages` | 18 | 15 | 7 | 3 | 68.2 (50.0 to 86.4) | 83.3 (64.7 to 100.0) | 75.0 (57.9 to 88.0) |
| `warranty_duration` | 14 | 10 | 7 | 4 | 58.8 (34.8 to 81.8) | 71.4 (46.2 to 93.3) | 64.5 (42.9 to 81.2) |
| `insurance` | 31 | 28 | 0 | 3 | 100.0 (100.0 to 100.0) | 90.3 (77.4 to 100.0) | 94.9 (87.3 to 100.0) |
| `covenant_not_to_sue` | 20 | 14 | 6 | 6 | 70.0 (50.0 to 89.5) | 70.0 (50.0 to 89.5) | 70.0 (52.4 to 84.8) |
| `third_party_beneficiary` | 5 (low) | 4 | 4 | 1 | 50.0 (14.3 to 83.3) | 80.0 (37.5 to 100.0) | 61.5 (22.2 to 87.5) |

## Cases skipped, by rule

| Field | Rule | Contracts |
|---|---|---|
| `agreement_date` | passage only | 1 |
| `agreement_date` | redacted | 11 |
| `effective_date` | passage only | 8 |
| `effective_date` | redacted | 9 |
| `expiration_date` | passage only | 19 |
| `expiration_date` | redacted | 5 |
| `renewal_term` | passage only | 3 |
| `notice_to_terminate_renewal` | passage only | 3 |

## Contracts without a record

None.
