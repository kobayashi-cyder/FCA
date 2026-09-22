# FCA — Fly Connectome Agent

FCA is an independent project that rebuilds useful engineering lessons from FAP around a **connectome-first core**.

FCA is not FAP renamed. FAP remains its own project. FCA treats the fly-inspired circuit as the primary computation model and attaches verification, memory, tooling, world state and bounded acceleration around it.

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
one selected organ/action
   ↓
outcome + verification
   ↓
dopamine-like prediction error
   ↓
local plasticity
   ↺
```

The executable neural core remains intentionally compact and deterministic:

- bounded sensory hashing;
- 256 KC-like sparse units;
- fixed compact fan-in wiring;
- top-16 competition;
- temporal trace;
- action-value readout;
- reward-prediction-error learning.

This is **connectome-inspired engineering**, not a claim that the complete Drosophila brain is simulated.

## v0.3 rebuild — lessons from FAP V87.34/V87.37/V87.39

The current rebuild keeps the neural controller unchanged and updates the runtime around it:

- **lazy specialist organs** — registered as factories and constructed only after the connectome selects them;
- **explicit WorldGraph** — typed entities, states, attributes, relations and negative relations;
- **fail-closed execution verification** — results are checked before positive learning is accepted;
- **verified hot paths** — optional native implementations are checked against the Python reference and fall back on mismatch/error;
- **observable sparsity** — registered vs loaded organs and load counts are visible at runtime.

The source lineage is documented in `docs/FAP_V87_39_REBUILD.md`.

## Earlier FAP knowledge carried forward

FCA also preserves established mechanisms outside the neural core:

- sparse selective activation instead of always-on monolithic processing;
- conversation / retrieval / verification / integration as replaceable organs;
- hot/cold memory and bounded working state;
- hypothesis competition and parallel candidate search;
- timeout and best-so-far behavior;
- verified Failure Memory;
- evidence gates and duplicate-safe promotion evidence;
- `ephemeral -> shadow -> consolidated`;
- regression quarantine and staged canary/rollback;
- candidate provenance and holdout separation;
- provider-neutral boundaries and bounded resource use;
- FAP V78 procedural circuits as bounded connectome-native priors;
- FAP V86 verified declarative skill composition outside the controller.

## Bounded code generation

FCA now includes a pure in-memory code-generation API derived from FAP's verified
code path. It converts a natural-language request into a compact `ProgramIR`,
emits Python source, and validates syntax plus a restrictive AST policy before
returning the candidate.

```python
from fca import FCACodeGenerator

generator = FCACodeGenerator()
result = generator.generate(
    "Pythonコードを作って。テキストから数字だけ抽出して合計する。"
)

assert result.ok
print(result.source)
print(result.ir.to_dict())
```

The generator does not write files, execute generated code, modify repositories,
or promote candidates. Those actions remain outside the generator and preserve
FCA's existing repository-coding approval boundary.

## Current execution shape

```text
goal / observation
  -> FCA sparse connectome
  -> MBON action competition
  -> LazyOrganRegistry loads exactly the selected specialist on first use
  -> specialist outcome
  -> IntegrityVerifier + optional critics
  -> accepted: original reward
     rejected: bounded negative teaching signal
  -> WorldGraph records action/outcome/acceptance relation
  -> MBON local plasticity
```

Run the full regression suite:

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

Those are capability targets to measure, not assume.

## Development rule

A feature belongs in FCA main only if it either:

1. strengthens the connectome-centered agent loop, or
2. is a bounded organ/control/acceleration layer that supports that loop without replacing it with an unrelated monolithic architecture.

Material departures belong on a separately named experimental branch/project.
