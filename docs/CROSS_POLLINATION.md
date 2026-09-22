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


## Repository host contract adapter

FAP repository coding execution remains outside FCA. A host may expose the
provider-neutral `fap.repository.host.v1` response as a plain JSON-like mapping.

FCA validates that mapping through `adapt_fap_repository_host()` before it can
be used by `RepositoryCodingOrgan`.

The adapter:

- imports no FAP module;
- accepts only the documented host metadata fields;
- rejects unknown fields so diffs/source/edit payloads cannot cross the boundary;
- validates state, SHA-256 identifiers, progress, attempt/repair bounds and safe
  reason codes;
- can wrap in-process or IPC transports with
  `repository_host_runner_from_mapping()`.

This keeps the dependency direction neutral:

`connectome selection -> FCA organ -> strict data contract -> host -> FAP`

FAP still owns repository planning, sandboxed edits and verification. FCA still
owns capability selection and evidence gating. Neither side gains automatic
promotion authority from this adapter.
