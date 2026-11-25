# pdfium-deepseek-flash on dev

- Run `01a2049b-6d35-74cf-a29f-07141c6e2e71` of configuration `pdfium-deepseek-flash` on the `dev` list, at commit `362ae1e121625c65d6dce5db5a5cbcfe55f8c470`.
- Model `accounts/fireworks/models/deepseek-v4p1-flash-1017`, prompt version 1, parser `pdfium`.
- Started 2026-11-22 18:53 UTC, ceiling $3.00.
- Contracts answered: **95 of 96** (1 failed, 95 valid). A contract without a record counts as null on every field, so what CUAD has in it is missed.
- Cost at list price: $0.6180, $6.44 per 1,000 contracts. Spent in this run: $0.5870; the rest came from the cache.
- Seconds per contract: mean 12.6, median 7.7, 95th percentile 31.0.

Scores are percentages, each with its 95% interval.

## Overall

|  | Precision | Recall | F1 |
|---|---|---|---|
| Micro (counts of all fields added) | 80.5 (78.0 to 82.8) | 86.5 (82.6 to 89.5) | 83.4 (80.8 to 85.5) |
| Macro (mean of the 41 fields) | 76.9 (72.4 to 80.4) | 83.3 (77.7 to 88.3) | 77.5 (71.8 to 80.4) |

## By field type

| Field type | Support | Precision | Recall | F1 |
|---|---|---|---|---|
| text | 96 | 89.5 (83.0 to 94.8) | 88.5 (82.3 to 94.8) | 89.0 (82.3 to 94.8) |
| entity_list | 273 | 90.3 (84.7 to 94.3) | 89.0 (80.1 to 94.6) | 89.7 (82.7 to 94.0) |
| date | 184 | 90.8 (86.4 to 94.6) | 85.3 (80.0 to 90.2) | 88.0 (83.8 to 91.4) |
| duration | 47 | 88.7 (79.1 to 96.2) | 100.0 (100.0 to 100.0) | 94.0 (88.3 to 98.0) |
| jurisdiction | 85 | 96.4 (91.6 to 100.0) | 94.1 (88.4 to 98.8) | 95.2 (90.2 to 98.9) |
| clause | 659 | 71.5 (67.4 to 75.0) | 83.6 (78.7 to 87.4) | 77.1 (73.5 to 80.0) |

## By field

Support is the number of CUAD answers: contracts, or party names. Under 10 it is marked low, and the score is not to be read alone.

| Field | Support | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| `document_name` | 96 | 85 | 10 | 11 | 89.5 (83.0 to 94.8) | 88.5 (82.3 to 94.8) | 89.0 (82.3 to 94.8) |
| `parties` | 273 | 243 | 26 | 30 | 90.3 (84.7 to 94.3) | 89.0 (80.1 to 94.6) | 89.7 (82.7 to 94.0) |
| `agreement_date` | 74 | 62 | 2 | 12 | 96.9 (91.9 to 100.0) | 83.8 (75.6 to 92.0) | 89.9 (83.7 to 95.2) |
| `effective_date` | 57 | 54 | 12 | 3 | 81.8 (71.9 to 91.0) | 94.7 (87.8 to 100.0) | 87.8 (80.8 to 93.5) |
| `expiration_date` | 53 | 41 | 2 | 12 | 95.3 (87.9 to 100.0) | 77.4 (66.0 to 87.8) | 85.4 (77.1 to 92.0) |
| `renewal_term` | 29 | 29 | 1 | 0 | 96.7 (88.6 to 100.0) | 100.0 (100.0 to 100.0) | 98.3 (93.9 to 100.0) |
| `notice_to_terminate_renewal` | 18 | 18 | 5 | 0 | 78.3 (60.0 to 94.4) | 100.0 (100.0 to 100.0) | 87.8 (75.0 to 97.1) |
| `governing_law` | 85 | 80 | 3 | 5 | 96.4 (91.6 to 100.0) | 94.1 (88.4 to 98.8) | 95.2 (90.2 to 98.9) |
| `most_favored_nation` | 4 (low) | 2 | 1 | 2 | 66.7 (0.0 to 100.0) | 50.0 (0.0 to 100.0) | 57.1 (0.0 to 100.0) |
| `competitive_restriction_exception` | 13 | 12 | 19 | 1 | 38.7 (22.2 to 56.7) | 92.3 (73.3 to 100.0) | 54.5 (35.0 to 71.2) |
| `non_compete` | 23 | 21 | 6 | 2 | 77.8 (60.0 to 92.0) | 91.3 (77.8 to 100.0) | 84.0 (70.8 to 93.3) |
| `exclusivity` | 32 | 28 | 6 | 4 | 82.4 (68.6 to 94.4) | 87.5 (75.0 to 97.1) | 84.8 (74.5 to 93.0) |
| `no_solicit_of_customers` | 8 (low) | 6 | 3 | 2 | 66.7 (33.3 to 100.0) | 75.0 (37.5 to 100.0) | 70.6 (36.4 to 90.9) |
| `no_solicit_of_employees` | 8 (low) | 8 | 2 | 0 | 80.0 (50.0 to 100.0) | 100.0 (100.0 to 100.0) | 88.9 (66.7 to 100.0) |
| `non_disparagement` | 3 (low) | 2 | 3 | 1 | 40.0 (0.0 to 100.0) | 66.7 (0.0 to 100.0) | 50.0 (0.0 to 88.9) |
| `termination_for_convenience` | 29 | 25 | 5 | 4 | 83.3 (69.0 to 96.0) | 86.2 (74.1 to 96.9) | 84.7 (73.7 to 93.8) |
| `right_of_first_refusal_offer_or_negotiation` | 12 | 11 | 1 | 1 | 91.7 (72.7 to 100.0) | 91.7 (75.0 to 100.0) | 91.7 (77.4 to 100.0) |
| `change_of_control` | 21 | 17 | 6 | 4 | 73.9 (55.6 to 90.9) | 81.0 (62.5 to 96.0) | 77.3 (61.5 to 89.7) |
| `anti_assignment` | 68 | 67 | 4 | 1 | 94.4 (88.6 to 98.7) | 98.5 (94.7 to 100.0) | 96.4 (92.9 to 99.3) |
| `revenue_or_profit_sharing` | 35 | 26 | 4 | 9 | 86.7 (73.7 to 97.0) | 74.3 (58.1 to 87.8) | 80.0 (66.7 to 89.6) |
| `price_restrictions` | 3 (low) | 3 | 20 | 0 | 13.0 (0.0 to 27.3) | 100.0 (100.0 to 100.0) | 23.1 (0.0 to 42.9) |
| `minimum_commitment` | 31 | 20 | 3 | 11 | 87.0 (70.8 to 100.0) | 64.5 (46.7 to 80.6) | 74.1 (59.1 to 85.3) |
| `volume_restriction` | 18 | 5 | 6 | 13 | 45.5 (14.3 to 76.9) | 27.8 (7.1 to 50.0) | 34.5 (9.5 to 55.2) |
| `ip_ownership_assignment` | 21 | 21 | 8 | 0 | 72.4 (56.5 to 88.6) | 100.0 (100.0 to 100.0) | 84.0 (72.2 to 93.9) |
| `joint_ip_ownership` | 8 (low) | 6 | 0 | 2 | 100.0 (100.0 to 100.0) | 75.0 (40.0 to 100.0) | 85.7 (57.1 to 100.0) |
| `license_grant` | 41 | 40 | 7 | 1 | 85.1 (74.5 to 95.0) | 97.6 (91.1 to 100.0) | 90.9 (84.0 to 96.6) |
| `non_transferable_license` | 24 | 22 | 9 | 2 | 71.0 (53.1 to 85.7) | 91.7 (77.8 to 100.0) | 80.0 (65.2 to 90.3) |
| `affiliate_license_licensor` | 3 (low) | 2 | 0 | 1 | 100.0 (100.0 to 100.0) | 66.7 (0.0 to 100.0) | 80.0 (0.0 to 100.0) |
| `affiliate_license_licensee` | 7 (low) | 7 | 2 | 0 | 77.8 (50.0 to 100.0) | 100.0 (100.0 to 100.0) | 87.5 (66.7 to 100.0) |
| `unlimited_license` | 3 (low) | 2 | 0 | 1 | 100.0 (100.0 to 100.0) | 66.7 (0.0 to 100.0) | 80.0 (0.0 to 100.0) |
| `irrevocable_or_perpetual_license` | 13 | 11 | 1 | 2 | 91.7 (71.4 to 100.0) | 84.6 (62.5 to 100.0) | 88.0 (70.6 to 100.0) |
| `source_code_escrow` | 3 (low) | 3 | 0 | 0 | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) | 100.0 (100.0 to 100.0) |
| `post_termination_services` | 35 | 34 | 47 | 1 | 42.0 (31.2 to 52.9) | 97.1 (89.7 to 100.0) | 58.6 (47.1 to 68.7) |
| `audit_rights` | 42 | 40 | 2 | 2 | 95.2 (87.5 to 100.0) | 95.2 (87.9 to 100.0) | 95.2 (90.0 to 99.0) |
| `uncapped_liability` | 12 | 10 | 30 | 2 | 25.0 (12.2 to 38.3) | 83.3 (60.0 to 100.0) | 38.5 (20.8 to 54.2) |
| `cap_on_liability` | 51 | 31 | 1 | 20 | 96.9 (89.3 to 100.0) | 60.8 (48.9 to 74.5) | 74.7 (64.3 to 84.4) |
| `liquidated_damages` | 18 | 15 | 7 | 3 | 68.2 (50.0 to 86.4) | 83.3 (64.7 to 100.0) | 75.0 (57.9 to 88.0) |
| `warranty_duration` | 14 | 9 | 7 | 5 | 56.2 (30.8 to 80.0) | 64.3 (36.4 to 90.0) | 60.0 (35.3 to 78.3) |
| `insurance` | 31 | 28 | 0 | 3 | 100.0 (100.0 to 100.0) | 90.3 (77.4 to 100.0) | 94.9 (87.3 to 100.0) |
| `covenant_not_to_sue` | 20 | 13 | 6 | 7 | 68.4 (46.7 to 88.9) | 65.0 (44.4 to 85.7) | 66.7 (47.6 to 82.8) |
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

| Contract | Status | Why |
|---|---|---|
| AIRSPANNETWORKSINC_04_11_2000-EX-10.5-Distributor Agreement.PDF | failed | could not connect on the last of 4 attempts |
