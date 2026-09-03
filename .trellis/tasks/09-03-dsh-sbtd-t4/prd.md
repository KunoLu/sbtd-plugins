# dsh-sbtd T4 manuals sync

Pin KunoLu/640-skills v1.0.13 SHA f8aa0d7225a26c5e00b81d2f1b05121108e63630. Host 0.1.1-rc.2.
Whitelist (12): book-ddd-distilled-modeling, book-ddia-data-design, book-legacy-change-safety, book-refactoring-pass, book-release-readiness, grill-with-docs, grill-me, grilling, domain-modeling, to-spec, to-tickets, trellis-workflow.
Copy SKILL.md, references/, and root markdown into manuals/<skill-id>/. Manifest path+sha256+revision. Script SOURCE or clone; copy from pinned git object. Fail closed.
No extra tools. No T5. No root README.

## Book Gate Plan
| Gate | Requirement | Lifecycle | Review |
| ddd | on-demand | not-required | |
| ddia | on-demand | not-required | |
| legacy | required | passed | characterized apply/hooks/plan unchanged |
| refactor | on-demand | not-required | |
| release | on-demand | not-required | unpublished |
