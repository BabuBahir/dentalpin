# Changelog — sistema_ts

## 0.1.0 (2026-09-09) — phase 1

- Opposition and item-type endpoints answer 404 for a patient or catalog
  item of another clinic (ownership check before the write).
- `SISTEMA_TS_CA_BUNDLE` for the test service's private Sogei CA; a clear
  `TLS:` error instead of the raw SSL trace.

- Per-clinic Sistema TS credentials (basic auth + RSA-encrypted pincode
  with the SanitelCF certificate), test/prod environments.
- Worker: paid patient invoices → `inserimento`, credit notes →
  `rimborso`, voids → `cancellazione`, opposition changes → `variazione`;
  synchronous SOAP service, backoff, `protocollo` stored with the XML.
- Per-patient opposition table and API; `tipoSpesa` per catalog item.
- Year overview (deadline 31 January, unsent/accepted/rejected counts).
