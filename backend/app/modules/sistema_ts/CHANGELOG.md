# Changelog — sistema_ts

## 0.1.0 (2026-09-09) — phase 1

- Per-clinic Sistema TS credentials (basic auth + RSA-encrypted pincode
  with the SanitelCF certificate), test/prod environments.
- Worker: paid patient invoices → `inserimento`, credit notes →
  `rimborso`, voids → `cancellazione`, opposition changes → `variazione`;
  synchronous SOAP service, backoff, `protocollo` stored with the XML.
- Per-patient opposition table and API; `tipoSpesa` per catalog item.
- Year overview (deadline 31 January, unsent/accepted/rejected counts).
