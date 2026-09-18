# FCA development rules

1. `main` is the connectome-first reference line.
2. FAP is a source of tested mechanisms, not a namespace to copy blindly.
3. Do not claim biological fidelity that is not measured.
4. Do not claim model parity from synthetic demos.
5. Unknown generated code is never activated directly.
6. Structural improvements require independent evidence.
7. Duplicate evidence cannot count twice.
8. Regressions trigger rollback/quarantine, not test weakening.
9. Keep resource budgets measurable: latency, RAM, disk, activation count.
10. Prefer local sparse learning for behavior; reserve code/circuit mutation for the verified outer loop.
11. External providers are replaceable organs behind explicit interfaces.
12. If a proposed architecture displaces the connectome core, develop it outside FCA main.
