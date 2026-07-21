# AI build log

This is a work-product record, not a transcript or private reasoning log.

## Phases and contributions

1. **Research and product selection.** ChatGPT GPT-5.6 Sol examined usability, competitive framing, novelty risk, and hackathon fit. The human selected the consequence-simulator direction and rejected inflated novelty claims.
2. **Fixture vertical slice.** Codex translated the thesis into Pydantic schemas, FastAPI routes, repository fixtures, impact traversal, test ranking, transparent risk factors, workflow estimates, scenario simulation, evaluation, and tests under `services/engine` and `fixtures`.
3. **Product onboarding.** ChatGPT critiqued a dashboard-first/fixture-first experience. Codex built the landing page, input flow, navigation, observed/predicted/suggested hierarchy, evidence UI, responsive behavior, and guided demo in `apps/web`.
4. **Public GitHub PR analysis.** The human prioritized a no-account judge path. Codex implemented canonical URL parsing, server-only optional authentication, bounded pagination, timeouts, rate-limit messages, patch normalization, provenance, and tests.
5. **User-provided inputs.** Codex added Git bundles and ZIP-plus-patch parsing with traversal, symlink, secret, binary, file-count, decompression, hook, filter, execution, and cleanup safeguards.
6. **Production hardening.** Codex corrected same-origin routing, CORS, hosted upload limits, Python locking, package assets, error handling, security headers, metadata, and deterministic fallback behavior.
7. **Vercel deployment.** Codex created the Services configuration, resolved CLI/schema and Python fixture-bundling failures, deployed preview/production, and exercised live routes. The human authenticated Vercel and retained release control.

## OpenAI use

At build time, ChatGPT GPT-5.6 Sol supported research, product reasoning, critique, and orchestration; Codex with GPT-5.6 performed most repository implementation, iteration, validation, integration, and deployment work. At runtime, the backend can call `gpt-5.6-sol` through the official Responses API using a compact evidence pack, evidence IDs, `store: false`, and a timeout. Numerical predictions remain deterministic. If the key, quota, model, safety system, or network is unavailable, the product returns a labelled deterministic explanation.

## Important corrections and bugs

- Replaced browser-visible localhost API defaults with same-origin production calls.
- Reduced advertised hosted uploads from 25 MB to a 3.5 MB total multipart budget.
- Added bounded GitHub pagination, optional token use, specific rate-limit/timeout behavior, and an outbound host allowlist.
- Prevented a local `.env.local` from entering Vercel builds.
- Declared runtime Python dependencies in `pyproject.toml`, generated `uv.lock`, and pinned Python 3.12.
- Moved prepared fixtures into the backend service bundle after production logs exposed invalid cross-service asset paths.
- Preserved fallback explanations instead of allowing optional OpenAI failures to block core analysis.

## Human review and remaining limits

Human review constrained research scope, required public judge input, rejected unsupported performance/novelty claims, tested outputs, and approved deployment decisions. The current risk, workflow, and scenario models remain heuristic; live analyses lack ground truth; structural test selection is not coverage-backed; public GitHub rate limits still apply; uploaded files are deliberately small; runtime GPT-5.6 requires a production key and must be verified before that claim is submitted.
