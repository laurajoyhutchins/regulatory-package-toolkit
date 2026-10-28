# Product boundary: public software, private regulatory data

BCAST follows the software/data ownership model established for Building Code Map. This is the **target architecture**, not a claim that migration is complete.

> **Open reusable software. Controlled regulatory evidence and production corpus.**

## Software authority: public `regulatory-package-toolkit`

This repository is the sole source of truth for reusable BCAST software and its semantics:

- provider-neutral publication/object identity, package contracts, schemas, compatibility and normative conformance;
- reusable, source-independent parsing/normalization primitives and deterministic compilation from a reviewed neutral input representation into BCAST packages;
- package validation, structural navigation, public client SDKs, CLI, reference server, public application/API behavior and tests;
- synthetic examples, public-safe test fixtures, and licensed-for-publication source adapters when independently approved;
- the canonical rules for materialization and content addressing. Private materializers must use these rather than implement an incompatible second compiler.

A public software checkout must be testable and useful with synthetic examples and, where rights permit, user-supplied lawful input. It must not need proprietary data, private credentials, or the private repository to pass its ordinary tests.

## Regulatory-data authority: private `regulatory-source-operations`

The private repository owns acquisition operations and data custody:

- live upstream retrieval, authentication, entitlements, source selection, provider-specific mappings/heuristics not cleared for publication;
- exact source bytes, source-rights decisions, producer records, private evidence, reviewed interpretations and operational audit history;
- production normalized records, cross-source mappings, corpus indexes, restricted fixtures and private data quality/acceptance decisions;
- jobs that execute the public compiler against authorized source material, verify source correspondence, retain generation-pinned evidence and produce reviewed distributions;
- service credentials, storage access, release controls and private operational integration checks.

Executable producer orchestration may remain private. Its **reusable domain algorithms** should move to public BCAST once reviewed for authorship, licensing and data leakage. Private code must not duplicate canonical package semantics.

Provider specificity alone is not a reason to close source. An eCFR or other adapter may be open if its implementation is independently releasable and does not disclose restricted data, mappings or access details. Conversely, public source availability does not grant permission to redistribute its compiled inputs or outputs.

## Single authority and dependency direction

```text
public BCAST contracts + library + deterministic builder
                  ^ pinned, versioned software dependency
                  |
private acquisition + review + authorized source data
                  |
                  v
       reviewed, rights-scoped BCAST packages
                  |
                  v
      public BCAST client / API / application
```

The public package builder owns package semantics; the private operation decides **which source bytes are authorized, reviewed, retained or published**. Public BCAST consumes ordinary conforming packages, not provider-native payloads. Private implementation pins a public revision and contract coordinate, never vendors another authoritative `spec/` tree.

Public code must not import private modules. Private operations may depend on pinned public code. No source bytes or restricted corpus enter public Git history, generated Pages content, sample releases, or CI artifacts. Publishing an algorithm never implies publishing source data; compiling data never creates redistribution rights.

A hosted consumer may serve only explicitly authorized packages. A public SDK, schema or API definition is not a promise of unrestricted corpus download, raw source access or bulk enumeration.

## Product boundaries with BCM and Arcata

BCAST represents **what an identified publication contains** and the limits of that representation. Building Code Map determines jurisdictional adoption and project applicability from independent evidence. Arcata performs and verifies engineering calculations. BCAST's `resolved` state is not a BCM `verified` determination, a legal-text certification, or an engineering approval.

## BCM / RSO regulatory evidence cutover note

See [BCAST publication identity versus BCM legal evidence](bcm-regulatory-evidence-consumer-boundary.md). In the planned cutover, private Regulatory Source Operations holds and reviews source-law evidence, amendments and effective dates and produces source-bound regulatory claims; public BCM handles geospatial authority and project applicability through its existing runtime. A source-neutral BCAST package establishes neither enactment nor a verified project verdict. The RSO-to-BCM claim export is a separate JSON Schema + ODCS contract with W3C PROV-O source lineage; it must not change BCAST package semantics or introduce an Overcenter dependency.

## Current implementation and migration

Today the public repository already owns package contracts, identities, validation, consumers, a CLI and a local read-only reference server. It now provides a reusable `build_package_v2` neutral-input compiler, but not a deployed production application.

The private `src/bcast_private/ecfr.py` supplies normalized eCFR source records to the public package builder, which derives every canonical BCAST package and object identity. Source-specific XML interpretation, independent source correspondence auditing, protected mappings, retention and rights decisions remain private. This is not evidence that production GCS readback or rights-reviewed distribution is complete.

Required cutover evidence:
1. Public synthetic compilation produces a conforming 0.2.0 package with stable identities and explicit unsupported/unresolved states, without private dependencies.
2. Private eCFR producer uses the pinned public builder; replay of the same source produces exactly the accepted package bytes/identity, or a deliberate versioned migration with independent evidence.
3. Private source-to-output coverage, rights guards, source retention and failure handling remain effective; public repositories and artifacts contain no restricted material.
4. Both CI lanes exercise the same package and failure cases; a successful private job pins the exact public revision; downstream public consumers remain independent of private provider APIs.
5. Remove duplicated package construction after equivalence, not before. A production service or real GCS archive is not claimed until separately verified.

See [Architecture](architecture.md) and [Source and rights](source-and-rights.md).
