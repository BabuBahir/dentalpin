# 0027 — Portugal: AT software certification decides the billing position for PT clinics

- **Status:** proposed
- **Date:** 2026-09-07
- **Deciders:** maintainers (@martinezsalmeron)
- **Tags:** compliance, billing, portugal, positioning

## Context

Issue #140 asks one question before anything else: **can an
open-source, self-hosted product be certified by the Autoridade
Tributária (AT) at all?** If not, DentalPin's honest position in
Portugal is "clinical record and schedule, invoice elsewhere". The
sources read are the primary texts as published by AT itself
(Decreto-Lei 28/2019 and Portaria 363/2010 in the consolidated PDFs
on info.portaldasfinancas.gov.pt), the AT FAQ on the certification
Portaria (DSPCIT, 12 pages), the AT FAQ on ATCUD/series
(faqs-00883) and the gov.pt service page for the certification
request. Points not confirmed from those are marked **open**.

### 1. Who must use a certified program

Art. 4 n.º 1 of Decreto-Lei 28/2019 obliges taxpayers with sede,
estabelecimento estável or domicílio in Portugal to use
"exclusivamente, programas informáticos que tenham sido objeto de
prévia certificação pela AT, sempre que: a) tenham tido, no ano civil
anterior, um volume de negócios superior a € 50 000 […]; b) utilizem
programas informáticos de faturação; c) sejam obrigados a dispor de
contabilidade organizada ou por ela tenham optado". AT applies the
three as alternatives. Condition b) is the one that matters here: a
practice that issues its invoices from DentalPin's `billing` module
*is* using an invoicing program, so the program must be certified
regardless of the practice's turnover. Art. 4 n.º 4: when the program
is down, invoices come from pre-printed typographic books and are
recovered into the program afterwards.

### 2. What certification requires (Portaria 363/2010, republished by Portaria 340/2013)

Art. 3 lists cumulative requirements:

- a) export of the SAF-T (PT) audit file (Portaria 321-A/2007, today
  Portaria 302/2016 and its current schema);
- b) "possuir um sistema que permita identificar a gravação do registo
  de faturas e documentos retificativos, através de um algoritmo de
  cifra assimétrica e de **uma chave privada de conhecimento exclusivo
  do produtor do programa**";
- c) access control with authentication of every user;
- d) "não dispor de qualquer função que, no local ou remotamente,
  permita alterar, direta ou indiretamente, a informação de natureza
  fiscal, sem gerar evidência agregada à informação original";
- e) the further technical requirements approved by despacho of the
  Director-General (Despacho 8632/2014).

Art. 6 defines the signature: RSA over
`InvoiceDate;SystemEntryDate;InvoiceNo;GrossTotal;previous Hash`,
stored with the key version in the program's database; every printed
document carries four characters of the signature (positions 1, 11,
21, 31), the text "Processado por programa certificado n.º …/AT" and
the document's unique id. Art. 4–5: the *empresa produtora* sends AT,
before commercialisation, an official declaration and the public key;
AT issues the certificate within 30 days, may run conformity tests at
any time (the producer must hand over a copy of the program and its
data dictionary), publishes the list of certified programs and
versions, and art. 5 n.º 5 says the certified version must observe the
requirements even when used by a non-obliged taxpayer. Art. 10:
revocation when the requirements stop being observed.

The AT FAQ makes the intent explicit: R9 — "o produtor de software ao
pedir a certificação […] assume que, independentemente do seu
utilizador, respeita os critérios"; R13 — later releases need no new
request but the producer commits to keep every requirement in every
later version, on pain of revocation; R21 — a multi-country program
must, when used by a Portuguese taxpayer, guarantee the rules; and
**R32 — tampering "só é possível se o utilizador conhecer a chave
privada da software house, que deve ser do conhecimento exclusivo do
produtor do programa, de outro modo a assinatura gravada não é
válida."**

### 3. The answer to the question

Nothing in the texts mentions licences. Open source is not the
obstacle; **self-hosting is**, for two independent reasons:

1. **The private key.** Art. 3 b) and FAQ R32 require the signing key
   to be known only to the producer. A practice that runs the code on
   its own server must hold the key at runtime to sign its invoices,
   so the key is no longer exclusive and the signature "não é
   válida". Cloud invoicing programs are certified precisely because
   the key stays on the producer's servers.
2. **The unalterable program.** Art. 3 d) and art. 5 (conformity
   tests against the version on file) treat the program as a fixed
   artefact of the producer. A practice that can and does modify the
   invoicing code path is running something the certificate does not
   cover; the certificate number printed on its invoices would be
   false.

Both objections disappear under one model, and only that one: a
**certified edition** in which (a) the signing step, and therefore
the private key, lives in a service operated by the producer (a
DentalPin-operated signing endpoint or a partner's), (b) the
installation sends the five signature fields and receives the
signature, and (c) the practice runs the certified version's billing
path unmodified — the same posture the AT already accepts for SaaS
programs. The producer must be an entity AT can certify (the request
is filed through the Portal das Finanças, so the producer needs a
Portuguese NIF; non-residents obtain one through a fiscal
representative — **open**: confirm with AT whether a non-resident
producer is accepted without a Portuguese establishment).

Everything else in the issue is ordinary work once that model exists:

- **ATCUD and series** (Portaria 195/2020; AT FAQ 4308/4536): every
  series is communicated to AT *before* first use, manually on the
  portal or through the producers' webservice, and AT returns a
  validation code (≥ 8 characters, no 0/1) immediately; ATCUD =
  `validation code-sequential number`, mandatory on every fiscally
  relevant document since 1 January 2023, without exemptions by
  volume or software (FAQ 4307).
- **QR code**: contents and placement per Portaria 195/2020 and AT's
  technical specification; carries NIFs, ATCUD, totals per tax rate,
  the four signature characters and the certificate number.
- **SAF-T (PT)**: export on demand (art. 3 a)) and monthly
  communication of issued invoices to AT by the 5th of the following
  month (art. 3 Decreto-Lei 198/2012 as amended by DL 28/2019),
  through the SAF-T file or the invoice webservice.
- **Dental services and IVA**: exempt under art. 9 n.º 1 CIVA (medical
  and dental professions); SAF-T exemption code `M07`.
- **Archive** (DL 28/2019 art. 19–21): 10 years, electronic archive
  with integrity controls, allowed anywhere in the EU, outside the EU
  only with prior AT authorisation — relevant to where a hosted
  edition is run.

### 4. Numbers that matter

| Item | Value | Source |
|---|---|---|
| turnover threshold (alternative condition) | € 50 000 | DL 28/2019 art. 4 n.º 1 a) |
| certificate issue term | 30 days, suspended during tests | Portaria 363/2010 art. 5 |
| invoice communication deadline | 5th of the following month | DL 198/2012 art. 3 (DL 28/2019) |
| ATCUD mandatory since | 1 January 2023 | Portaria 195/2020, AT FAQ |
| archive | 10 years | DL 28/2019 art. 19 |

## Decision

1. **DentalPin, as an open-source product the practice installs and
   may modify, cannot be an AT-certified invoicing program.** The
   blocker is art. 3 b)/d) of Portaria 363/2010 (producer-exclusive
   private key, unalterable program), not the licence.
2. **DentalPin's position in Portugal is "clinical record and
   schedule; invoice with a certified program"** until a certified
   edition exists. The website's Portuguese pages and the country
   readiness matrix say so plainly; a `PT` clinic sees `billing`'s
   invoice issuing disabled with that explanation (budgets, treatment
   plans and payments stay).
3. The only viable path to invoicing is a **certified edition**:
   producer-held key behind a remote signing service, a frozen billing
   code path, ATCUD series webservice, QR code and SAF-T (PT) export,
   filed for certification by an entity with a Portuguese NIF. This
   ADR records the shape so the door stays open; it does not commit
   anyone to building it.
4. No `pt_at` module is started until a producer decides to run the
   signing service and file the certification.

## Consequences

### Good

- The website stops implying something the law forbids, which is the
  outcome the issue asked for in the "no" case.
- The certified-edition shape is written down with its legal anchors,
  so a future producer (DentalPin the company, or a Portuguese
  partner) can cost it instead of re-reading the Portaria.

### Bad / accepted trade-offs

- A Portuguese practice cannot invoice from DentalPin today; the
  product is weaker in Portugal than the UI translation suggests.
- The certified edition is a hosted dependency inside a self-hosted
  product; some users will reject that on principle.

## Alternatives considered

- **Certify the self-hosted build and ship the private key with it.**
  — Violates art. 3 b) as read by AT (FAQ R32); the signatures would
  be invalid and the certificate revocable.
- **Let the practice generate its own key pair.** — The practice is
  not the producer; the certificate is issued to the producer's
  program and key.
- **Ignore certification for small practices.** — DL 28/2019 art. 4
  n.º 1 b) applies to anyone using an invoicing program; no volume
  exemption survives (FAQ 4307 for ATCUD).
- **Build ATCUD/QR/SAF-T now and certify later.** — Wasted until the
  key/hosting question is decided; the ADR keeps the design instead.

## How to verify the rule still holds

- `docs/technical/country-readiness.md` lists PT billing as "not
  available: AT certification"; the Portuguese landing page repeats
  it.
- Backend test: a clinic with country `PT` gets `409` from the issue
  endpoint of `billing` with the certification message (once the gate
  is implemented).

## References

- Issue #140; `backend/app/modules/billing/`; ADR 0025 (Italy, the
  same "positioning first" pattern)
- Decreto-Lei 28/2019 (AT consolidated PDF):
  <https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/legislacao/diplomas_legislativos/Documents/Decreto_Lei_28_2019.pdf>
- Portaria 363/2010 as republished by Portaria 340/2013 (AT PDF):
  <https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/legislacao/diplomas_legislativos/Documents/Portaria_363_2010.pdf>
- AT/DGCI FAQ "Certificação de software" (DSPCIT), questions 4, 9,
  13, 16, 21, 22, 32
- AT FAQ Séries/ATCUD (4307, 4308, 4536, 4701):
  <https://info.portaldasfinancas.gov.pt/pt/apoio_contribuinte/questoes_frequentes/Pages/faqs-00883.aspx>
- gov.pt, "Pedir certificação de programa de faturação":
  <https://www.gov.pt/servicos/programa-de-faturacao-certificacao>
- Portaria 195/2020 (ATCUD, QR); Portaria 302/2016 (SAF-T PT);
  Despacho 8632/2014 (technical requirements); DL 198/2012 art. 3;
  CIVA art. 9
