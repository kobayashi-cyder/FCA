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
- ingest normalized neuron/edge tables — generic PN→KC CSV converter implemented;
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
Status: sandbox/holdout gate and external evaluator controller integrated; candidate generation provider next.

- Failure Memory — implemented;
- capability-gap clustering/prioritization — implemented;
- candidate generation — provider boundary next;
- sandbox/holdout evaluator controller — implemented;
- sandbox/resource/holdout gates — evidence-isolated gate implemented;
- sandbox and holdout evidence must both pass before SHADOW;
- latency and memory regressions quarantine candidates;
- SHADOW -> 5/20/50/100 staged canary -> CONSOLIDATED — integrated;
- rollback and quarantine — integrated across evidence and canary stages;
- provenance chain — implemented.

## FCA-6 — Distillation into circuit priors
Status: initial native integration implemented.

- distill repeated provider/teacher behavior into compact local rules — FAP V78 Gemma 4 circuit import implemented;
- attach procedural priors to sparse KC/MBON action competition without replacing the connectome core — implemented;
- preserve teacher-derived factual-looking memory as unverified shadow state — implemented;
- seed Hot/Cold Memory and ConceptGraph through explicit import functions — implemented;
- promote only repeatedly verified patterns;
- measure capability retained per byte/RAM/latency;
- prefer irreversible compact structure when it preserves verified behavior.
