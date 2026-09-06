# INSTRUCTION.md — handler handoff (razorpay module)

This file is a handoff for an agent running on a machine with the full
Python/Docker toolchain. It summarizes what was done and exactly what
still needs to be run/verified. Branch: `feat/razorpay-payments`
(tracks `babubahir/feat/razorpay-payments`).

> **Delete this file** once the remaining work below is done and pushed.
> It is a transient handoff only — do not merge it into the product.
> ```bash
> git rm INSTRUCTION.md && git commit -m "chore: remove razorpay handoff file" && git push babubahir feat/razorpay-payments
> ```

## What is here

Refactor of PR #373's Razorpay online-payment integration into a
standalone `razorpay` module (issue #263), resolving Martin's
(martinezsalmeron) review points.

> NOTE: the branch was rebuilt onto latest `origin/main` as a **single
> squashed commit** (the feature diff only — no merge commits). The
> original per-step commits were rewritten. Do not expect the old
> hashes (`9ce2ecfd`, `6349a1d6`, `5bda7fac`) to exist anymore.

## Getting started on the new machine

1. Clone the fork and check out the branch (it tracks
   `babubahir/feat/razorpay-payments`; push to `babubahir`, never to
   `origin` — you have no write access to `dentalpin/dentalpin`):
   ```bash
   git clone https://github.com/BabuBahir/dentalpin
   cd dentalpin
   git pull
   git checkout feat/razorpay-payments
   git remote add origin https://github.com/dentalpin/dentalpin   # if not present
   git fetch origin   # always rebase/verify against latest main
   ```
   If you cloned *after* the branch was already rewritten on GitHub, the
   checkout above is enough. If you have an old local copy, hard-reset to
   the rewritten branch:
   ```bash
   git fetch babubahir && git reset --hard babubahir/feat/razorpay-payments
   ```
2. Prerequisites: Python 3.11+, `uv`, Docker + Docker Compose, Node 22 +
   npm (frontend is npm — `package-lock.json`, not bun/pnpm).
3. Install deps + lock (**must be first** — the backend Docker image
   installs from `uv.lock` (issue #356), and it is currently stale since
   pyproject.toml gained `razorpay>=1.4.0`):
   ```bash
   cd backend && uv sync && uv lock
   ```
   Then `cd .. && docker compose up -d --build` so the backend image picks
   up the updated lock.
4. Frontend deps (only needed for frontend checks):
   ```bash
   cd frontend && npm ci
   ```
5. Demo login for manual verification: `admin@demo.clinic` / `demo1234`
   (seed data: `./scripts/seed-demo.sh` after a fresh DB).

Key decisions (do NOT revisit unless you find a bug):
- Per-clinic Fernet-encrypted keys (`app.core.email.encryption`), never returned.
- Server-side flow: create order -> checkout -> verify signature
  (stdlib `hmac`/`compare_digest`) -> re-fetch captured payment ->
  amount/currency/method from the gateway -> `record_payment` with
  `idempotency_key=f"razorpay:{payment_id}"`.
- `razorpay` is NOT added to `PAYMENT_METHODS`/`PaymentMethod`; method is
  mapped onto the closed list (upi/netbanking/card/other).
- `manifest.depends = ["payments"]`; own Alembic branch `razorpay`
  (rp_0001, table `razorpay_settings`).
- Frontend via `payments.collect.actions` slot (IN-gated) + registerSettingsPage.
- The `payments` module must remain clean (= commit `57f7c536`).

## Done (verify, do not redo)

- payments module reverted to `57f7c536` (only `backend/alembic.ini` +
  `backend/pyproject.toml` wiring differ intentionally).
- `backend/app/modules/razorpay/`: `__init__.py`, `models.py`, `schemas.py`,
  `service.py`, `router.py`, `migrations/versions/rp_0001_initial.py`,
  `CLAUDE.md`, `CHANGELOG.md`, `frontend/`.
- `backend/tests/modules/razorpay/`: `test_settings_router.py`,
  `test_verify_router.py`, `test_permissions.py`, `test_uninstall_roundtrip.py`.
- `backend/pyproject.toml`: dep `razorpay>=1.4.0` + entry point `razorpay`.
- `backend/alembic.ini`: `version_locations` gained razorpay migrations.
- `frontend/app/config/permissions.ts`: `razorpay` permission block.
- `frontend/modules.json`: razorpay layer added manually (validate against
  the generator output — this is normally written at runtime).
- `docs/technical/razorpay/{overview,permissions,events}.md`.

## PR #373 review compliance (martinezsalmeron, Sep 6) — verify on the new machine

| # | Review point | Status in this branch | What the new machine must verify |
|---|---|---|---|
| 1 | Separate gateway module, not inside `payments` | Done — standalone `razorpay` module + slot | `payments/` clean vs `57f7c536`; module boots |
| 2 | Keys per-clinic, not global settings | Done — Fernet-encrypted `razorpay_settings` | settings round-trip tests |
| 3 | Amount verified server-side | Done — re-fetch, assert `captured` + order match, record gateway amount/currency | `test_verify_router.py` (amount/currency from gateway, tamper rejected) |
| 4 | Replay / idempotency | Done — `idempotency_key=f"razorpay:{payment_id}"` | replay test returns original payment, no double row |
| 5 | Currency mismatch | Done — order uses `ctx.clinic.currency`; recorded currency from capture | currency paths in `test_verify_router.py` |
| 6 | `razorpay` not a valid method | Done — mapped onto closed list; id in `reference` | confirm `razorpay` NOT in `PAYMENT_METHODS` |
| 7 | Dependency must be locked | **PENDING here** — `backend/uv.lock` stale; needs `uv lock` (bootstrap step 3) | `uv lock` passes; backend image installs razorpay |
| 8 | Frontend flow (swallowed errors, stale submit state, hard-coded English, competing buttons) | Mostly done — slot button (no competing buttons), error toast in handler, i18n. `modal.ondismiss` intentionally not set (reload covers it) | frontend lint/typecheck + manual IN-clinic checkout |
| 9 | CI: lint import order, N818 name, no-`any`, Nuxt UI colors | Done in code — `RazorpayNotConfiguredError`, typed `razorpay.d.ts`, `neutral` color | `ruff`, `npm run lint`, `npm run typecheck:layers` |
| 10 | Tests, CHANGELOG, docs | Done — 4 test files, module CLAUDE/CHANGELOG, `docs/technical/razorpay/*` | full pytest suite (razorpay + all modules) |

The reviewer also asked for a **design sketch in issue #263** before
implementation — that is a conversation point on GitHub (tresundios
offered to drive it), not a code task here. Decide separately.

## Remaining (requires Python/Docker — the reason for this handoff)

1. **Regenerate catalogs** (this was NOT done, CI will fail until you do):
   ```bash
   cd backend && python  ;# or: docker-compose exec backend python -m ...
   python scripts/generate_catalogs.py
   git status  # should now show docs/modules-catalog.md + docs/events-catalog.md updated
   ```
   Verify the commit (don't hand-edit the catalogs — the generated output
   is the source of truth and CI checks for drift):
   ```bash
   git add docs/modules-catalog.md docs/events-catalog.md
   git commit -m "docs: regenerate module catalog (razorpay)"
   ```
2. **Backend tests + lint**:
   ```bash
   docker-compose up -d db
   docker-compose exec backend python -m pytest tests/modules/razorpay -v
   docker-compose exec backend pytest -q            # full suite
   cd backend && ruff check . && ruff format --check .
   ```
   Watch for: alembic head resolution on the `razorpay` branch, and the
   `test_uninstall_roundtrip` downgrade step.
3. **uv lock** — already covered in bootstrap step 3; the `uv.lock` diff
   from that step should land in the final commit so CI doesn't fail on
   drift. It will show up as a modified `backend/uv.lock` — include it.
4. **Frontend lint + typecheck** (module layer is wired via the committed
   `frontend/modules.json`):
   ```bash
   cd frontend && npm run lint
   npm run typecheck:layers   # stop the frontend container first; modules.json auto-restores
   ```
   The `useRazorpay`/`useRazorpayCountry` auto-imports in the components
   and the `registerSlot`/`registerSettingsPage` typing are the main
   things NOT yet verified by a real build.

## Known open items / trade-offs

- `reloadNuxtApp()` full reload after a successful payment — deliberate
  (ModuleSlot does not forward emits); validates during frontend manual test.
- `frontend/modules.json` was hand-edited; verify it matches the runtime
  generator (layers array, modules array, `sort_keys` order).
- `docs/modules-catalog.md` / `docs/events-catalog.md` still need
  regeneration (step 1) — do not hand-edit them.
- The `razorpay` SDK is used only for order creation + payment fetch;
  signature verification is stdlib-only. Do not switch to the SDK helper.

## Useful reference points

- Clean payments reference: commit `57f7c536` (#365 final).
- Per-clinic encrypted settings + migration + settings page pattern:
  `backend/app/modules/whatsapp_webhook/`.
- Module authoring source of truth: `docs/technical/creating-modules.md`.

## Wrapping up (after the remaining steps pass)

1. Before finishing, re-sync with the latest upstream and fix any drift:
   ```bash
   git fetch origin
   git rebase origin/main
   # re-run: generate_catalogs.py, backend tests+ruff, frontend lint/typecheck
   ```
2. Delete this file (command at the top), then commit the follow-up work
   (`uv.lock`, regenerated catalogs, etc.) as one or more commits:
   ```bash
   git add -A
   git commit -m "chore(razorpay): lockfile, catalogs, follow-up verification"
   ```
3. Push to the fork (never to origin):
   ```bash
   git push babubahir feat/razorpay-payments
   ```
4. The PR already exists in the dentalpin fork — or open one from
   `babubahir:feat/razorpay-payments` into `dentalpin/dentalpin:main`.
