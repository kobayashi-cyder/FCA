# FCA ↔ FAP cross-pollination

FCA and FAP remain separate projects. They exchange **verified mechanisms**, not identity.

## FAP → FCA

Current imports:
- bounded goal-completion contracts;
- planner/executor/critic separation;
- explicit success criteria;
- stall/failure/replan limits;
- checkpointable/approval-aware control concepts;
- verification, canary, rollback, quarantine and provider-boundary lessons from earlier FAP releases.

## FCA → FAP

Current exports:
- sparse capability activation;
- relevance/value/information-gain/cost scheduling;
- connectome-manifest discipline;
- local reward-prediction-error learning as a low-cost behavioral layer;
- explicit separation between fast local adaptation and slow verified structural change.

## Exchange capsule

Cross-project mechanisms use `fca-fap.exchange.v1` capsules containing:
- source project;
- exact source commit;
- capability name;
- mechanism description;
- evidence;
- constraints;
- canonical SHA-256 digest.

A capsule is provenance, not automatic permission to activate code.


## Verified repository-coding evidence

FAP V87.71 source commit:
`67538f84e33cfc8aa2dae4cba42857bdb33b3e8c`

FAP may export `repository_coding_verified_candidate` evidence through the existing `fca-fap.exchange.v1` capsule.

The capsule is intentionally inert. It contains provenance and hashes, not executable edits:

- plan ID and repository digest;
- goal SHA-256 instead of goal text;
- file paths, operations and before/after SHA-256 values;
- bounded verification facts;
- optional successful local candidate-branch provenance;
- explicit constraints forbidding automatic activation or promotion.

FCA receives this through `RepositoryEvidenceImporter`.

Receiving a valid capsule only enters the existing `ExchangeRegistry`. It does not create an organ, execute code, modify MBON action selection, or advance directly to `SHADOW`/`ACCEPTED`.

Independent FCA evidence is still required for state promotion. Duplicate receipt does not count as new evidence.
