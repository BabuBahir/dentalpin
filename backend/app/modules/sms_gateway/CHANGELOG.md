# Changelog - sms_gateway module

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial module (roadmap issue #231, PR2): SMS delivery via pluggable
  providers on the notifications `ChannelAdapter` contract.
- `sms_gateway_settings` table (own Alembic branch `smg_0001`):
  per-clinic provider key, Fernet-encrypted credentials, from-number,
  active flag.
- `log` placeholder backend (records + reports success, sends
  nothing) + provider registry for future Twilio-style backends;
  unimplemented providers fail honestly at send and `/test` time.
- System SMS templates (`smg_0002`, 9 keys x es/en): template-kind sends
  render body text instead of dispatching empty; downgrade removes only
  seeded rows.
- RBAC: `sms_gateway.settings.read/write`, admin-only. No agent tools.
