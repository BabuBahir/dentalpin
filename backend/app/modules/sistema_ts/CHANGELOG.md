# Changelog — sistema_ts

## Unreleased — phase 2

- Nuxt layer: Settings → Billing pages "Sistema Tessera Sanitaria"
  (credentials, certificate upload, identity, year overview with the
  31 January deadline, `tipoSpesa` per catalog item) and "Sistema TS
  submissions" (states, protocollo, retry, send now); opposition card in
  the patient summary; submission panel on the invoice page; ten locales.

## 0.1.0 (2026-09-09) — phase 1

- Per-clinic Sistema TS credentials (basic auth + RSA-encrypted pincode
  with the SanitelCF certificate), test/prod environments.
- Worker: paid patient invoices → `inserimento`, credit notes →
  `rimborso`, voids → `cancellazione`, opposition changes → `variazione`;
  synchronous SOAP service, backoff, `protocollo` stored with the XML.
- Per-patient opposition table and API; `tipoSpesa` per catalog item.
- Year overview (deadline 31 January, unsent/accepted/rejected counts).
