# CredLens unified platform: status, how to run, honest limits

Branch `platform-modification`. Nothing here is committed: the team commits by hand.

## What exists now (Phases 0 to 6, backend and frontend)

| Area | Where |
|---|---|
| Four platform admins from `.env`, Argon2id, 12-character password policy, rate limits | `src/accounts/`, `.env.example` |
| Company self-registration (first Credit Officer owns the company), invitation codes for FSRs and Credit Officers | `src/accounts/registration.py`, `invitations.py`, `/register`, `/app/invitations` |
| Merchant onboarding: typed details to prefilled consent PDF, or blank form to hand-filled upload; 11-section English and Bangla consent; EasyOCR reading; human verification (a different officer when one exists, else recorded as `self_verified`) | `src/onboarding/`, `src/extraction/` |
| FSR assignment, daily sheet grid (keyboard, paste from Excel, autosave, submit, amend, phone cards), imports from CSV, Excel, Word, PDF and photos | `src/daily/`, `web/src/pages/fsr/` |
| Credit Officer monitoring: submissions, accept or return, notifications bell | `/app/submissions`, `NotificationBell.tsx` |
| Stored assessments, company range policy, recompute check, decisions linked to an assessment | `src/assessment/`, `src/api/routes_assessments.py`, `/app/range-policy` |

## Run it

```bash
python tasks.py init-db        # empty operational database (data/credlens.db)
python tasks.py admins         # creates the platform admins listed in .env (never prints passwords)
python tasks.py ocr-setup      # one-time download of the OCR models
python tasks.py api            # API on :8000
python tasks.py app            # dashboard on :5173
python -m src.extraction.worker  # reads scanned documents in the background
```

The old `data/app.db` is untouched. No real database migration has been run.

## Range policy

The product ships **no approved policy**. Until a company's owner approves one on the Range policy
page, assessments show the score and reasons and no range. The engine uses verified purchases
only (rows that reached the contract tables through a submitted daily sheet or an officer's
entry). Sales are stored and shown, not used. Every number is the company's own.

## Honest limits

- The model is trained on synthetic data only (validation AUC 0.71). It has not been validated on real repayments. A first-time borrower with no repayment history usually shows "Needs more info": coverage is low by design.
- EasyOCR does not support handwriting. Printed forms are read by zone; handwritten registers are read poorly and every such row is flagged for correction. The handwriting accuracy benchmark has not been run.
- The consent text is a draft stamped as such. In production only a template approved by a platform admin with a legal-review reference is issued. It has not been reviewed by Bangladesh counsel. The retention period is a placeholder to be set by Legal.
- Work emails are unverified (no email delivery). Password resets are admin-issued codes.
- Daily-sheet records show "Typed in by staff" provenance on the merchant page; a dedicated "daily sheet" label is not yet added.
- Audit-log text and some benchmark pages still use the older wording.

## Suggested CLAUDE.md changes (needs the lead's decision; not made)

"No real partner data" and "synthetic on every screen" conflict with a real multi-company platform. Suggest: keep the model-provenance line on assessment screens, and drop the screen-wide synthetic banner for company workspaces.

## Suggested commit commands (run yourselves)

```bash
git status
git add src tests config docs web requirements.txt tasks.py .env.example
git commit -m "Unified multi-company platform: accounts, onboarding, daily records, assessments"
```
