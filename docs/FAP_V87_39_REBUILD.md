# FCA rebuild from FAP V87.39-era mechanisms

This rebuild intentionally transfers mechanisms, not FAP's media-specific identity.

## Verified source points

- FAP V87.34 Scene Graph 2: commit `36d0530af4dad799a829c54521b82d311fcaac8e`
  - explicit objects, states, relations, negative constraints and verification.
- FAP V87.37 Sparse End-to-End Execution: commit `5ad4c1543777296b5f2ed37a90ebacfcbf1c17c7`
  - top-1 sparse routing, lazy organ loading, cached specialists and observable sparsity.
- FAP V87.39 Native Geometry + Sparse LBS: commit `fdb9c0cd5d7bab6c1eda1c1496558c0b483de64a`
  - native hot loops behind a portable boundary with retained fallback paths.

## FCA translation

FCA keeps the connectome controller unchanged:

```text
observation
  -> SensoryHash
  -> sparse KenyonLayer
  -> MBON competition
  -> one action/organ
  -> outcome
  -> reward-prediction-error plasticity
```

Around that core, v0.3 adds:

1. `LazyOrganRegistry`
   - factories are registered without loading specialists;
   - only the connectome-selected organ is constructed;
   - loaded organs are cached and observable.

2. `WorldGraph`
   - typed entities, state, attributes and positive/negative relations;
   - task/world state can be checked explicitly rather than hidden in free text.

3. `FCARebuiltRuntime`
   - connectome selection remains first;
   - execution is followed by fail-closed verification;
   - rejected outcomes receive a bounded negative teaching signal;
   - action/outcome/acceptance relations are recorded in the world graph.

4. `VerifiedHotPath`
   - the Python reference remains authoritative;
   - a native backend is accepted only after equivalence checking;
   - exception or mismatch permanently falls back to the reference path.

## Boundary

This is not a copy of FAP's image renderer, geometry engine or scene objects.
Those are specialist organs. FCA adopts the scheduling, verification, world-state
and acceleration patterns while keeping its fly-connectome-inspired controller
as the system's center.
