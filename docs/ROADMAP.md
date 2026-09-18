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
Next.

- hot/cold episodic memory;
- semantic concept graph;
- activation cost per organ;
- value-of-information scheduling;
- branch pruning and timeouts;
- contradiction retention.

## FCA-3 — Data-backed connectome wiring
Next major biological step.

- define a versioned wiring manifest;
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
- Failure Memory;
- capability-gap clustering;
- candidate generation;
- sandbox/resource/holdout gates;
- ephemeral -> shadow -> staged canary -> consolidated;
- rollback and quarantine;
- provenance chain.

## FCA-6 — Distillation into circuit priors
- distill repeated provider/teacher behavior into compact local rules;
- promote only repeatedly verified patterns;
- measure capability retained per byte/RAM/latency;
- prefer irreversible compact structure when it preserves verified behavior.
