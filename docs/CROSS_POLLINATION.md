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
