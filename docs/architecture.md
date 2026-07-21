# Architecture

The local monorepo separates presentation from consequence modeling. `apps/web` is a strict TypeScript Next.js App Router client. It requests fixture metadata, analysis, and counterfactual simulations from the versioned FastAPI API in `services/engine`. The engine loads immutable JSON fixtures and composes replaceable impact, test, risk, workflow, action, and explanation components.

The baseline is evidence-first: dependency traversal emits paths, test selection emits reasons, risk emits additive factor contributions, and workflow predictions expose their bottleneck and confidence. No output is authored in React and no external model is called.

## Request flow

1. Select a prepared PR in the web sidebar.
2. Fetch the PR and POST analysis/simulation requests concurrently.
3. Traverse the repository graph in both directions up to two hops with decay.
4. Rank mapped tests and apply a conservative fallback for critical/shared modules.
5. Combine bounded, documented risk factors and workflow history.
6. Apply action adjustments and rank them with centralized weights.
7. Render evidence and a deterministic, locally generated explanation.

The fixtures are synthetic and intentionally cover low, medium, and high consequence profiles. Static fixture storage is sufficient because this version has no mutable user state.

## User-supplied evidence

`uploads.py` is an anti-corruption layer around the existing domain and predictors. Public GitHub
metadata, Git bundle comparisons, and project ZIP plus patch inputs become ordinary `Repository`
and `PullRequest` objects before `AnalysisService` runs. Uploaded results therefore use the same
impact, test, risk, workflow, action, explanation, evidence, and provenance contracts.

`TemporaryStorage` defines the replaceable storage boundary. Its local implementation creates a
unique operating-system temporary workspace and deletes it on success or failure. Git bundles are
inspected as bare repositories with hooks and interactive behavior disabled; user trees are never
checked out and repository code is never executed. ZIP input is bounded and held in memory.

Missing evidence is represented rather than invented. A project and diff has structural capability,
heuristic test durations, reduced confidence, and unavailable workflow ETA. Bundles add local commit
history but still lack hosted CI and review history. JavaScript/TypeScript import analysis is enhanced;
other languages use an explicit generic fallback.
