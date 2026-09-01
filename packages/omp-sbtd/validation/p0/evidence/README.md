# Compatibility evidence layout

Content-addressed, append-only evidence and attestation bundles referenced by
`../compatibility-ledger.v1.json` entries live here.

Rules:

- Every file is stored under a content-addressed path derived from its SHA-256
  (`evidence/<sha256>.json`); ledger `evidenceLocator` and
  `attestationBundleLocator` values point into this directory.
- A new bundle is reviewed in the same controlled bot PR as the first
  assessment entry that references it.
- Files are never deleted or modified while any ledger entry references them;
  GitHub Actions artifacts are temporary transport only and never the sole
  copy or a long-term locator.
- Only sanitized content is committed: event names, schema-validity verdicts,
  ordering summaries, reason codes and digests. Never commit profiles, tokens,
  raw transcripts, model output or PII.
- Local, fork, manual or otherwise untrusted runs are `local-observation`
  material: they are never committed here as trusted evidence, never written
  to the public ledger, and never change the derived support matrix.

- Historical assessments attested under `KunoLu/KPi` before the cutover to
  `KunoLu/sbtd-plugins` are preserved verbatim in
  `../compatibility-ledger.kunolu-kpi-legacy.v1.json`. That archive is not the
  active ledger: `compatibility-matrix validate` and public matrix derivation
  read only `../compatibility-ledger.v1.json`, which accepts only provenance
  matching `compatibility-trust-policy.v1.json` (`repository`:
  `KunoLu/sbtd-plugins`). Legacy evidence bundles remain here while the
  archive references them; do not rewrite their KPi provenance.

