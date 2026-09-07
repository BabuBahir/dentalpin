# 0028 — France: SESAM-Vitale homologation and the billing position for FR clinics

- **Status:** proposed
- **Date:** 2026-09-07
- **Deciders:** maintainers (@martinezsalmeron)
- **Tags:** compliance, billing, france, positioning

## Context

Issue #141 asks whether an open-source, self-hosted product can be
homologated to produce *feuilles de soins électroniques* (FSE), and
what is minimally useful if not. Sources: GIE SESAM-Vitale's public
pages for éditeurs (cahier des charges, technologies supportées,
éditeurs PS libéraux, home page), the CNDA (Centre national de dépôt
et d'agrément of the Assurance Maladie) "référencer un logiciel" mode
opératoire, the ANS pages on HDS and on the Ségur programme for
chirurgiens-dentistes. Points not confirmed from those are marked
**open**.

### 1. What producing an FSE requires

Two gates, both attached to a **publisher and a version**:

1. **CNDA agrément.** The publisher "télécharge et signe le contrat de
   service proposé par le CNDA (protocole d'agrément SESAM-Vitale,
   conditions générales et particulières)", receives a *Numéro
   d'Identification Éditeur* (NIE) giving access to the test
   resources, develops against the GIE's reference documents,
   validates on the CNDA test environments, submits a *dossier de
   recette*, then passes the CNDA's own test sessions (on site or
   remote, "la base intégrale du guide de tests"), repeated until
   compliant. "L'attestation de conformité du CNDA est délivrée au
   logiciel pour un n° de version donné" and the version is published
   on the CNDA site.
2. **GIE SESAM-Vitale homologation** (Commission de Validation et
   d'Homologation, CVH) of the integration of the GIE's *composants
   SESAM-Vitale* per the *Cahier des charges Éditeurs*, currently
   **CDC 1.40 – Addendum 8 (April 2025)**, covering FSE/DRE, Vitale
   card reading, e-prescription, INSi and ADRi. The components are
   distributed by the GIE through its *espace industriels* (access on
   request) and support Windows, macOS and Linux 64-bit, plus Citrix;
   they run on the workstation that holds the card reader (PC/SC,
   homologated readers) and the professional's CPS/e-CPS.

For liberal professionals (dentists included) the expected service
set is FSE, DRE, tiers payant, ADRi, ALDi, SCOR, e-prescription,
AATi/DMTi/IMTi, INSi, DMP, HRi and Vitale card update (TMAJ). No
dentist-specific derogation appears on the GIE pages.

Costs of the CNDA contract and of the component licence are not
published on the pages read — **open** (they are commonly described
as free of charge, but no official text was found saying so).

### 2. Does open source, self-hosted, fit?

Nothing forbids an open-source publisher from signing the CNDA
contract. What does not fit is *self-hosted and modifiable*:

- the agrément and the homologation are per version; a practice that
  runs a modified build runs an unagreed version, exactly as in
  Portugal (ADR 0027);
- the SESAM-Vitale components are proprietary binaries licensed to
  the publisher; they cannot be committed to a public repository, so a
  self-hosted build would have to fetch them from the GIE at install
  time under the publisher's licence — **open** whether the licence
  allows that distribution model;
- the components, the reader and the CPS live on the workstation, so
  a browser-based product needs a local agent per workstation (the
  way web-based LGCs do it), which is a second deliverable to
  homologate.

The realistic route for a project like this is therefore the one the
market already uses: **integrate a homologated *moteur de facturation
SESAM-Vitale*** from a specialised vendor (several exist; the GIE
lists them among éditeurs), where the engine vendor holds the
homologation and DentalPin is the LGC feeding it. Whether the LGC
still needs its own CNDA attestation when it drives such an engine is
**open** and is the first question to put to the CNDA.

### 3. Beyond FSE: HDS and Ségur

- **HDS** (art. L.1111-8 Code de la santé publique; référentiel
  approved by the arrêté of 26 April 2024): any third party hosting
  health data for a French practice must be HDS-certified; a
  practice hosting its own system for its own patients is **not**
  subject to it. That is the line the issue asked us to write down:
  self-hosted DentalPin needs no HDS; any DentalPin-operated hosting
  for French practices does.
- **Ségur du numérique, vague 2, LGC chirurgiens-dentistes**: state-
  funded (SONS) referencing of practice software on INS, DMP feeding,
  MSSanté, Pro Santé Connect and e-prescription; the funding window
  for LGC publishers opened on the Ségur portal in February 2026. It
  is an incentive for the publisher and an expectation of the market,
  not a legal condition for a practice to use a given software.

## Decision

1. **DentalPin does not pursue SESAM-Vitale homologation as a
   self-hosted open-source product.** The gates are per publisher and
   per version, rest on proprietary workstation components, and would
   not survive a practice modifying its own build.
2. **DentalPin's position in France is "clinical record, schedule and
   billing outside the Assurance Maladie flow"**: invoices and paper
   *feuilles de soins* the patient sends themselves; no FSE, no tiers
   payant. The French pages and the country readiness matrix say so.
3. The path to FSE, if a producer wants it, is a **connector module
   (`FR`-gated) to a homologated billing engine** from a vendor that
   holds the CNDA/GIE approvals, with the workstation agent supplied
   by that vendor. The first step is the two open questions to the
   CNDA (LGC attestation when driving an engine; component
   distribution model), not code.
4. **HDS**: self-hosted installations are out of scope of HDS; any
   hosted offer for French practices requires an HDS-certified host.
   Write this on the French pages instead of hedging.
5. Ségur referencing (INS, DMP, MSSanté, PSC) is tracked as a separate
   product decision; it is independent of FSE and does not change
   points 1–3.

## Consequences

### Good

- Clear French positioning; no more "coming soon" for a feature that
  needs a publisher programme we have not entered.
- The connector route keeps FSE reachable without owning proprietary
  components or a workstation agent.

### Bad / accepted trade-offs

- No tiers payant means a French practice keeps a second tool for
  billing the Assurance Maladie; DentalPin is a clinical/scheduling
  product there.
- The connector route makes FSE depend on a commercial vendor's
  engine and licence.

## Alternatives considered

- **Enter the CNDA programme directly and homologate DentalPin.** —
  Per-version agrément on a product users rebuild themselves, plus a
  workstation agent and proprietary components in a public repo; not
  compatible with the project's model.
- **Read the Vitale card only (identity), skip FSE.** — Card reading
  uses the same licensed components and reader; it does not escape
  the programme, and INSi needs a CPS-authenticated call.
- **Ship nothing and say nothing.** — The issue exists because the
  hedging costs credibility; the honest sentence is the deliverable.

## How to verify the rule still holds

- The country readiness matrix and the French landing page state
  "billing outside the Assurance Maladie flow; no FSE/tiers payant;
  self-hosted installations outside HDS".
- No module under `backend/app/modules/` claims SESAM-Vitale
  capability without a CNDA attestation number in its docs.

## References

- Issue #141; issue #142 (French e-invoicing reform, separate);
  ADR 0027 (Portugal, same pattern)
- GIE SESAM-Vitale, Cahier des charges Éditeurs (CDC 1.40 Addendum 8,
  April 2025): <https://www.sesam-vitale.fr/web/sesam-vitale/cahier-des-charges>
- GIE SESAM-Vitale, Technologies supportées:
  <https://www.sesam-vitale.fr/web/sesam-vitale/technologies-supportees>
- GIE SESAM-Vitale, Éditeurs PS libéraux:
  <https://www.sesam-vitale.fr/web/sesam-vitale/ps-liberaux1>
- CNDA, Référencer un logiciel — mode opératoire:
  <https://cnda.ameli.fr/editeurs/referencer-un-logiciel/mode-operatoire/>
- ANS, HDS: <https://esante.gouv.fr/produits-services/hds>; art.
  L.1111-8 CSP; arrêté du 26 avril 2024
- ANS, Ségur du numérique pour les chirurgiens-dentistes:
  <https://esante.gouv.fr/segur/chirurgiens-dentistes>
