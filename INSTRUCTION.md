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

## Remaining (requires Python/Docker — the reason for this handoff)

1. **Regenerate catalogs** (this was NOT done, CI will fail until you do):
   ```bash
   cd backend && python  ;# or: docker-compose exec backend python -m ...
   python scripts/generate_catalogs.py
   git status  # should now show docs/modules-catalog.md + docs/events-catalog.md updated
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
3. **uv lock** for the new package — REQUIRED before CI
   (pyproject.toml already declares `razorpay>=1.4.0`, but main's
   `backend/uv.lock` is stale; CI fails on drift until this runs):
   ```bash
   cd backend && uv lock
   ```
4. **Frontend lint + typecheck** (needs backend to wire the layer first —
   run `docker-compose up -d backend frontend`, or regenerate modules.json):
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
