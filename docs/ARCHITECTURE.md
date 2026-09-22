# FCA architecture

## 1. Architectural invariant

The connectome-inspired loop is the system's center of gravity.

```text
Sense → Sparse representation → Competition/Inhibition → Value → Action → Outcome → Plasticity
```

Language models, search systems, code factories, media models and tools are **organs/providers**. They may supply observations or specialist results, but they do not replace the core controller.

## 2. Circuit mapping

| FCA element | Fly-inspired analogy | Engineering role |
|---|---|---|
| `SensoryHash` | sensory/PN projection | bounded input channels |
| `KenyonLayer` | mushroom-body Kenyon cells | sparse high-dimensional representation |
| top-k winner selection | inhibition/competition | sparse activation budget |
| `TemporalTrace` | persistent/eligibility-like activity | short context across turns |
| `MBONPolicy` | mushroom-body output channels | competing actions |
| reward-prediction error | dopamine-like teaching signal | local plasticity |
| action | motor/behavioral output | selected organ/tool/response |

The analogy is functional, not a biological-fidelity claim.

## 3. v0.3 sparse execution plane

FAP V87.37 demonstrated that a mature stack can recover sparsity by routing before specialist construction. FCA adopts that mechanism without importing FAP's media identity.

```text
observation
  -> sparse FCA controller
  -> one MBON-selected action
  -> LazyOrganRegistry
       -> construct selected organ on first use
       -> cache loaded organ
  -> organ result
  -> fail-closed verification
  -> accepted/rejected teaching signal
  -> WorldGraph state update
  -> local plasticity
```

The important invariant is ordering: **the connectome selects before the specialist is loaded**.

## 4. Explicit world/task state

FAP V87.34 made objects, states, relations and negative constraints explicit rather than leaving all semantics in prompt text.

FCA generalizes that into `WorldGraph`:

- typed entities;
- explicit state;
- string-normalized attributes;
- positive relations;
- negative relations;
- deterministic snapshots.

The graph is a task-state substrate, not a renderer.

## 5. Verified acceleration boundary

FAP V87.38/V87.39 moved hot loops into portable C99 while retaining older paths as fallbacks.

FCA represents the same engineering rule with `VerifiedHotPath`:

```text
Python reference
    ↕ first-use equivalence check
optional native backend
```

Requirements:

- native path must be deterministic and side-effect-free;
- Python behavior remains authoritative;
- mismatch disables native execution;
- native exception disables native execution;
- fallback is automatic for that runtime instance.

This lets future C/Rust/WASM hot loops accelerate FCA without redefining FCA's semantics.

## 6. FAP-derived outer control plane

FAP's verified-improvement work remains a metacognitive capability layer:

```text
runtime outcome
  → verified failure classification
  → Failure Memory
  → capability-gap priority
  → candidate organ/circuit modification
  → static/resource/sandbox tests
  → untouched evidence
  → ephemeral
  → shadow
  → staged canary
  → consolidated OR rollback/quarantine
  → production evidence
  ↺
```

This separation matters: learning in the core can be fast/local, while structural capability changes require stronger evidence.

## 7. Memory

FCA keeps three timescales:

- **trace memory**: turns/local eligibility state;
- **working/hot memory**: current task context and active concepts;
- **cold memory**: durable episodic/semantic records, paged in selectively.

## 8. Organs

Typical organs include:

- conversation;
- retrieval;
- decomposition;
- verification;
- integration;
- web/tool use;
- code generation/repair;
- vision/image;
- STT/TTS;
- environment adapters.

The default v0.3 direction is top-1 sparse activation for specialist execution. Parallel candidate generation can still occur *inside* a selected bounded organ when justified.

## 9. Autonomy rule

A user goal is maintained state, not one prompt/one answer.

```text
goal
 → observe
 → select next action
 → execute selected organ
 → verify
 → evaluate progress
 → update state
 → repeat until terminal criterion / budget / blocker
```

The controller must distinguish completion, recoverable failure, blocker, low-confidence state and unsafe/unverified structural change.

## 10. Resource rule

FCA targets practical operation on modest hardware:

- sparse activation;
- lazy organ construction;
- bounded context;
- deterministic paging;
- timeouts;
- branch pruning;
- resource-aware candidate promotion;
- optional native hot paths with verified fallback;
- optional providers loaded only when useful.
