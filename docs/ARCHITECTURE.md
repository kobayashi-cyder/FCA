# FCA architecture

## 1. Architectural invariant

The connectome-inspired loop is the system's center of gravity.

```text
Sense → Sparse representation → Competition/Inhibition → Value → Action → Outcome → Plasticity
```

Language models, search systems, code factories, media models and tools are **organs/providers**. They may supply observations or candidate actions, but they do not replace the core controller.

## 2. Circuit mapping

| FCA element | Fly-inspired analogy | Engineering role |
|---|---|---|
| `SensoryHash` | sensory/PN projection | bounded input channels |
| `KenyonLayer` | mushroom-body Kenyon cells | sparse high-dimensional representation |
| top-k winner selection | inhibition/competition | sparse activation budget |
| `TemporalTrace` | persistent/eligibility-like activity | short context across turns |
| `MBONPolicy` | mushroom-body output channels | competing actions |
| reward-prediction error | dopamine-like teaching signal | local plasticity |
| action | motor/behavioral output | tool, response, inspect, wait, etc. |

The analogy is functional, not a biological-fidelity claim.

## 3. FAP-derived outer control plane

FAP's strongest engineering work is retained as a metacognitive safety and capability layer:

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

This separation matters: learning in the core can be fast/local, while structural code/capability changes require stronger evidence.

## 4. Memory

FCA should keep three distinct timescales:

- **trace memory**: milliseconds/turns; local recurrent/eligibility state;
- **working/hot memory**: current task context and active concepts;
- **cold memory**: durable episodic/semantic records, paged in selectively.

FAP's Hot/Cold Memory, GC and bounded conversation ideas should be reused here rather than keeping all state resident.

## 5. Organs

Planned organs:

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

Organs compete for activation budget. Only relevant organs should run.

## 6. Autonomy rule

A user goal should be represented as a maintained goal state, not as one prompt/one answer.

```text
goal
 → observe
 → select next action
 → execute
 → evaluate progress
 → update state
 → repeat until terminal criterion / budget / blocker
```

The controller must distinguish:
- task completion;
- recoverable failure;
- external blocker;
- low-confidence state;
- unsafe/unverified structural change.

## 7. Resource rule

FCA targets practical operation on modest hardware. Resource use is therefore a first-class objective:

- sparse activation;
- bounded context;
- deterministic paging;
- timeouts;
- branch pruning;
- resource-aware candidate promotion;
- optional providers loaded only when useful.
