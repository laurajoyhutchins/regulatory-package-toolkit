# BCAST publication identity versus BCM legal evidence

Status: boundary clarification for the cross-repository BCM cutover prepared 2026-10-28; no new public BCAST format or source release is proposed. See [public BCM #41](https://github.com/laurajoyhutchins/building-code-map/issues/41) and [RSO #77](https://github.com/laurajoyhutchins/arcata-rso/issues/77).

## Stable separation of concerns

**BCAST:** canonical published work identity, edition, revision, sections/tables, content-addressed object/package semantics, structural navigation and conformance. A complete BCAST package may describe a law, model code or standard that has **never been enacted** in a location.

**Regulatory Source Operations:** lawful source acquisition and source review, exact passage authenticity, enacted/amended/repealed instruments, effective intervals and exceptions, review/rights custody, W3C PROV-O derivation and source-bound regulatory claim evidence. The private source producer invokes the pinned BCAST builder, never duplicates package identity logic.

**Building Code Map:** governmental entity and geospatial identity, dated territory, address/parcel and enforcement authority, project applicability and the single canonical verified/not-verified project verdict. BCM consumes source evidence only through its independently approved legal-evidence policy and public Runtime.

**No new cross-product kernel:** dependency-closure ideas may be implemented in RSO's regulatory domain without importing Overcenter. BCAST does not evaluate legal enactment, scope inheritance or project geometry. Source evidence and BCAST object identity may be linked by immutable reference but are not the same assertion.

## Consumer contract rules

- Regulatory claim exports from private RSO to BCM need **paired JSON Schema and ODCS**, version pins, exact legal source/anchor hashes and actual review scope. They must carry uncertainty and counterevidence.
- W3C PROV-O describes source custody/transformation lineage. It cannot independently authenticate original source text or approve a claim.
- BCAST package 0.2 representation status (resolved, unresolved, unsupported) conveys **representation availability only**. Do not translate it into regulatory adoption or BCM verified status.
- Private source bytes/reviewer material stay under lawful custody; no protected corpus in this public repo, release assets, or source-history import.
- BCAST package specs and content addressing remain defined exclusively by this public repository. Do not alter them merely to accommodate a private provider field; link identities at the RSO->BCM adapter instead.
- Without source-law review and separate effective geographic authority, public BCM must remain conditional or not_verified.

## Acceptance and scope

A consumer test should establish that the same pinned BCAST publication can be referenced by an RSO adoption claim for one reviewed jurisdiction while remaining unadopted or unknown elsewhere. Hostile cases include wrong edition, false policy authorization, changed source anchor, contrary ordinance and date mismatch. They belong to RSO/BCM contract conformance rather than to the source-neutral BCAST package validator.

This document does not establish a production custody transfer, legal review, standard-source fidelity, completed rule compiler or deployed BCM provider. See [BCAST product boundary](product-boundary.md).
