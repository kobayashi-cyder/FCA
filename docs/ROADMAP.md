# FCA roadmap

## FCA-0 — Connectome-first executable core
Status: implemented.

- bounded sensory channels;
- sparse KC-like representation;
- competition/inhibition;
- temporal trace;
- MBON-like action channels;
- reward-prediction-error learning;
- FAP-derived verified candidate lifecycle.

## FCA-1 — Persistent autonomous goal loop
Status: initial implementation.

- maintained goal state;
- observe/select/execute/evaluate/repeat;
- explicit completion, blocker and budget states;
- specialist-organ registry;
- no one-prompt/one-answer assumption.

## FCA-2 — Memory and organ economics
Status: initial implementation.

- hot/cold episodic memory — implemented;
- semantic concept graph — implemented;
- activation cost per organ — implemented;
- value-of-information scheduling — implemented;
- branch pruning and timeouts;
- contradiction retention — implemented;
- hypothesis generation/competition — implemented.

## FCA-3 — Data-backed connectome wiring
Status: manifest/import boundary implemented; real dataset ingestion next.

- define a versioned wiring manifest — implemented;
- ingest explicit neuron/edge tables;
- preserve neuron classes and compartment metadata where available;
- compare synthetic sparse wiring against data-backed wiring;
- benchmark behavior, latency and memory;
- never silently substitute synthetic wiring while claiming biological wiring.

## FCA-4 — Specialist organs
- conversation;
- retrieval/search;
- verification;
- code repair;
- vision/image;
- STT/TTS;
- environment/tool adapters.

FAP V69–V77 boundaries should be reused where they remain valid.

## FCA-5 — Verified structural self-improvement
Status: control-plane skeleton implemented; sandbox/holdout integration next.

- Failure Memory — implemented;
- capability-gap clustering/prioritization — implemented;
- candidate generation;
- sandbox/resource/holdout gates;
- ephemeral -> shadow -> staged canary -> consolidated — skeleton implemented;
- rollback and quarantine — lifecycle/canary triggers implemented;
- provenance chain — implemented.

## FCA-6 — Distillation into circuit priors
- distill repeated provider/teacher behavior into compact local rules;
- promote only repeatedly verified patterns;
- measure capability retained per byte/RAM/latency;
- prefer irreversible compact structure when it preserves verified behavior.
