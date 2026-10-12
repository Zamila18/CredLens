# DATA_REQUEST_SHOPUP.md: what to ask ShopUp for, and how to manage it

The prototype runs on synthetic data. Real data, if ShopUp agrees, is a bonus for validation and must never block the build.

## Ask in tiers
1. Minimum: a data dictionary and a few sample rows (no real identities) for purchases, deliveries, payments and loans, so our schema and adapter match reality.
2. Better: a pseudonymised extract for 300 to 1,000 merchants, 12 to 18 months, with loan outcomes (repaid within 30 days of due date or not).
3. Best: consent basis for each merchant, plus a documented definition of "default" and of "late".

## Fields (map to our tables)
- merchants: pseudonymous merchant_id, onboarding date, district, town tier, shop type, licence yes/no.
- purchases (Mokam, what the merchant buys): purchase id, merchant_id, date, amount, category.
- deliveries (REDX): parcel id, merchant_id, order id if available, dispatched/delivered timestamps, status (delivered/returned/failed/cancelled), COD flag, COD remitted on time.
- payments/loans (Baki): loan id, merchant_id, issue date, limit, due dates, paid dates, amounts, outcome.
- No names, phone numbers, addresses, NID numbers.

## Conditions to propose
Pseudonymised IDs (hash with a key ShopUp keeps); data stays on one encrypted machine or a private folder, never in the Git repo; access limited to named team members; used only for the hackathon and deleted after, with written confirmation; no re-identification attempts.

## How to manage what arrives
- Keep a data register (spreadsheet): file name, date received, who sent it, what it contains, row counts, checksum, where stored, who may access, deletion date.
- Put raw files in a read-only folder outside the repo; build cleaned tables from scripts; log every transformation.
- Validate on arrival: duplicate IDs, orphan rows, date order, missing rates, outcome definition; report issues back to ShopUp.
- Map to our schema in `src/adapters/shopup_real.py`; never edit raw files.
- Run the same pipeline; report results separately from synthetic results and say they are on a small sample.

## Who to contact
Roles, not names, unless ShopUp gives them: the hackathon liaison, a data/privacy lead, a credit or risk lead, a product/partnership contact. Confirm names through APRU or ShopUp before writing to anyone.
