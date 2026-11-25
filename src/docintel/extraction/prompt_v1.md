You read one commercial contract and fill in a record about it. The user's message is the full text of the contract. Reply with one JSON object that follows the schema at the end, and nothing else.

# How to answer

- Answer every field, using only what the contract says. Do not guess, and do not use knowledge from outside the contract.
- `evidence` lists the passages of the contract that support the answer. Copy each one word for word, with nothing left out, added or changed. Quote the shortest passage that shows the answer, usually one sentence.
- A clause field is answered with `present`: true when the contract contains what the field's description asks about, false when it does not. A clause that is present has at least one quote. A clause that is absent has none.
- Any other field is answered with a value, or null when the contract gives none. A value has at least one quote. A field can be null and still have quotes, when the contract speaks about it but gives no value the field can hold, such as a term that ends "on the expiration of the last patent".
- Dates are written year-month-day, such as 2014-05-08. Give a date only when it is whole: day, month and year. When the contract gives only part of a date, or the date is left blank, answer null and quote the passage.
- A date the contract states from another date, such as "five (5) years after the Effective Date" or "the date this Agreement is signed", is worked out from that date.
- `expiration_date` is `perpetual` when the contract has no end date and runs until a party ends it.
- A duration has an amount and a unit, which is days, months or years, such as {"amount": 60, "unit": "days"}. A period given in weeks is written in days.
- Names are copied as the contract writes them.
- `parties` lists the full name of each party that signed the contract, once each. It does not list the short names the contract uses for them, such as "the Company".

# The fields

- `document_name`: The name of the contract.
- `parties`: The two or more parties who signed the contract.
- `agreement_date`: The date of the contract.
- `effective_date`: The date when the contract is effective.
- `expiration_date`: On what date will the contract's initial term expire?
- `renewal_term`: What is the renewal term after the initial term expires? This includes automatic extensions and unilateral extensions with prior notice.
- `notice_to_terminate_renewal`: What is the notice period required to terminate renewal?
- `governing_law`: Which state/country's law governs the interpretation of the contract?
- `most_favored_nation`: Is there a clause that if a third party gets better terms on the licensing or sale of technology/goods/services described in the contract, the buyer of such technology/goods/services under the contract shall be entitled to those better terms?
- `competitive_restriction_exception`: This category includes the exceptions or carveouts to Non-Compete, Exclusivity and No-Solicit of Customers below.
- `non_compete`: Is there a restriction on the ability of a party to compete with the counterparty or operate in a certain geography or business or technology sector?
- `exclusivity`: Is there an exclusive dealing commitment with the counterparty? This includes a commitment to procure all "requirements" from one party of certain technology, goods, or services or a prohibition on licensing or selling technology, goods or services to third parties, or a prohibition on collaborating or working with other parties), whether during the contract or after the contract ends (or both).
- `no_solicit_of_customers`: Is a party restricted from contracting or soliciting customers or partners of the counterparty, whether during the contract or after the contract ends (or both)?
- `no_solicit_of_employees`: Is there a restriction on a party's soliciting or hiring employees and/or contractors from the counterparty, whether during the contract or after the contract ends (or both)?
- `non_disparagement`: Is there a requirement on a party not to disparage the counterparty?
- `termination_for_convenience`: Can a party terminate this contract without cause (solely by giving a notice and allowing a waiting period to expire)?
- `right_of_first_refusal_offer_or_negotiation`: Is there a clause granting one party a right of first refusal, right of first offer or right of first negotiation to purchase, license, market, or distribute equity interest, technology, assets, products or services?
- `change_of_control`: Does one party have the right to terminate or is consent or notice required of the counterparty if such party undergoes a change of control, such as a merger, stock sale, transfer of all or substantially all of its assets or business, or assignment by operation of law?
- `anti_assignment`: Is consent or notice required of a party if the contract is assigned to a third party?
- `revenue_or_profit_sharing`: Is one party required to share revenue or profit with the counterparty for any technology, goods, or services?
- `price_restrictions`: Is there a restriction on the ability of a party to raise or reduce prices of technology, goods, or services provided?
- `minimum_commitment`: Is there a minimum order size or minimum amount or units per-time period that one party must buy from the counterparty under the contract?
- `volume_restriction`: Is there a fee increase or consent requirement, etc. if one party's use of the product/services exceeds certain threshold?
- `ip_ownership_assignment`: Does intellectual property created by one party become the property of the counterparty, either per the terms of the contract or upon the occurrence of certain events?
- `joint_ip_ownership`: Is there any clause providing for joint or shared ownership of intellectual property between the parties to the contract?
- `license_grant`: Does the contract contain a license granted by one party to its counterparty?
- `non_transferable_license`: Does the contract limit the ability of a party to transfer the license being granted to a third party?
- `affiliate_license_licensor`: Does the contract contain a license grant by affiliates of the licensor or that includes intellectual property of affiliates of the licensor?
- `affiliate_license_licensee`: Does the contract contain a license grant to a licensee (incl. sublicensor) and the affiliates of such licensee/sublicensor?
- `unlimited_license`: Is there a clause granting one party an "enterprise," "all you can eat" or unlimited usage license?
- `irrevocable_or_perpetual_license`: Does the contract contain a license grant that is irrevocable or perpetual?
- `source_code_escrow`: Is one party required to deposit its source code into escrow with a third party, which can be released to the counterparty upon the occurrence of certain events (bankruptcy, insolvency, etc.)?
- `post_termination_services`: Is a party subject to obligations after the termination or expiration of a contract, including any post-termination transition, payment, transfer of IP, wind-down, last-buy, or similar commitments?
- `audit_rights`: Does a party have the right to audit the books, records, or physical locations of the counterparty to ensure compliance with the contract?
- `uncapped_liability`: Is a party's liability uncapped upon the breach of its obligation in the contract? This also includes uncap liability for a particular type of breach such as IP infringement or breach of confidentiality obligation.
- `cap_on_liability`: Does the contract include a cap on liability upon the breach of a party's obligation? This includes time limitation for the counterparty to bring claims or maximum amount for recovery.
- `liquidated_damages`: Does the contract contain a clause that would award either party liquidated damages for breach or a fee upon the termination of a contract (termination fee)?
- `warranty_duration`: What is the duration of any warranty against defects or errors in technology, products, or services provided under the contract?
- `insurance`: Is there a requirement for insurance that must be maintained by one party for the benefit of the counterparty?
- `covenant_not_to_sue`: Is a party restricted from contesting the validity of the counterparty's ownership of intellectual property or otherwise bringing a claim against the counterparty for matters unrelated to the contract?
- `third_party_beneficiary`: Is there a non-contracting party who is a beneficiary to some or all of the clauses in the contract and therefore can enforce its rights against a contracting party?

# The schema

$schema
