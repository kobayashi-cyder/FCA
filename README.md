# FCA — Fly Connectome Agent

FCA is an independent project that rebuilds the useful engineering lessons from FAP around a **connectome-first core**.

FCA is not FAP renamed. FAP remains its own project. FCA treats the fly-inspired circuit as the primary computation model and attaches FAP-derived verification, memory, tooling and self-improvement controls around it.

## Core loop

```text
observation
   ↓
sensory projection
   ↓
sparse KC-like expansion
   ↓
global competition / inhibition
   ↓
MBON-like action channels
   ↓
action
   ↓
outcome / reward
   ↓
dopamine-like prediction error
   ↓
local plasticity
   ↺
```

The current implementation is intentionally small and deterministic:

- bounded sensory hashing;
- 256 KC-like sparse units;
- fixed compact fan-in wiring;
- top-16 competition;
- temporal trace;
- action-value readout;
- reward-prediction-error learning.

This is **connectome-inspired engineering**, not a claim that the full Drosophila brain or its exact biological dynamics are simulated.

## FAP knowledge carried forward

FCA preserves the strongest FAP ideas outside the neural core:

- sparse selective activation instead of always-on monolithic processing;
- conversation / retrieval / verification / integration as replaceable organs;
- hot/cold memory and bounded working state;
- hypothesis competition and parallel candidate search;
- timeout and best-so-far behavior;
- verified Failure Memory;
- evidence gates;
- duplicate-safe promotion evidence;
- `ephemeral -> shadow -> consolidated`;
- regression quarantine;
- canary rollout / rollback concepts;
- candidate provenance and holdout separation;
- provider-neutral chat/image/audio/tool boundaries;
- bounded resource use.

See `docs/FAP_LINEAGE.md` and `docs/ARCHITECTURE.md`.

## Current status

The current FCA mainline establishes the executable core, verified-improvement skeleton, and a connectome-native import of FAP V78's Gemma 4 distilled procedural circuits.

The V78 import does **not** turn FCA into an LLM. The 10 distilled circuits are converted into bounded priors over existing MBON-like action channels *after* FCA computes its sparse KC pattern. Reward-prediction-error learning remains active, while 22 teacher memories stay explicitly shadow/unverified and 27 concept relations are imported as unverified facts.

Run:

```bash
python -m unittest discover -s tests -v
```

## Non-goals

FCA currently does not claim:

- LLM-level world knowledge;
- a biologically complete fly connectome;
- autonomous arbitrary code deployment;
- verified image/STT/TTS backends;
- GPT-5.6-class language quality.

Those are capability targets to be measured, not assumed.

## Development rule

A feature only belongs in FCA main if it either:

1. strengthens the connectome-centered agent loop, or
2. is a bounded organ/control layer that supports that loop without replacing it with an unrelated monolithic architecture.

Material departures belong on a separately named experimental branch/project.
