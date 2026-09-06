# Changelog — nav_online module

## Unreleased

- feat(#341): initial release — phase 1 of NAV Online Számla reporting:
  `BillingComplianceHook` for HU snapshotting issued invoices / credit
  notes as Online Számla 3.0 `InvoiceData` XML (TAM exemption + 27 %
  lines, PRIVATE_PERSON/DOMESTIC customers, STORNO), a queued worker
  doing tokenExchange → manageInvoice → queryTransactionStatus with
  backoff and retry, test/prod environments, settings + records pages.
