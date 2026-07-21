# Submission pack

## Project name

IMerge

## Tagline

See what a code change may affect before it merges.

## Category

Developer Tools

## Short description

IMerge analyzes a proposed code change and predicts its likely impact, relevant tests, engineering risk, workflow delays, and safest next action. It turns a public GitHub PR, Git bundle, or project patch into one evidence-backed consequence view, with optional GPT-5.6 explanations grounded in deterministic outputs.

## Full description

Pull requests affect more than changed lines: they alter dependency paths, invalidate test assumptions, create operational risk, and influence how quickly a team reaches a green, reviewable candidate. Existing tools usually expose those concerns separately, leaving reviewers to assemble the consequence story manually.

IMerge provides one unified, evidence-first workflow. A judge can paste a previously unseen public GitHub PR without creating an account, upload a small Git bundle, upload a small project ZIP plus patch, or use a guided synthetic example. The backend normalizes the change into repository and workflow evidence, traverses likely dependency impact, ranks structural tests, computes inspectable risk factors, estimates workflow outcomes where evidence supports them, and compares six next-action scenarios. The UI keeps observed facts, predictions, and suggestions visually distinct and exposes confidence, limitations, and provenance.

The system uses Next.js, FastAPI, GitHub REST APIs, a repository graph, deterministic/statistical consequence baselines, and the OpenAI Responses API. GPT-5.6 receives a compact evidence pack and explains existing results; it does not replace or fabricate numerical predictions. The Vercel Services deployment provides a single public domain and same-origin API routing. Uploaded code is processed temporarily and never executed.

This Builder Week prototype is judge-testable today, but honest about limitations: test recommendations are structural without coverage, risk is not production-calibrated, workflow estimates need history, scenarios are not causal guarantees, and hosted uploads are capped at 3.5 MB.

## How it was built

Next.js renders the product and guided fixture. FastAPI handles GitHub ingestion, safe uploads, repository normalization, graph traversal, predictors, scenario comparison, and explanations. GitHub requests are canonical, bounded, timed, and optionally authenticated server-side. Vercel Services routes `/api/*` and `/health` to Python and everything else to Next.js.

## How Codex was used

Codex with GPT-5.6 implemented most of the monorepo: typed schemas, FastAPI endpoints, fixtures, dependency traversal, test selection, risk/workflow baselines, scenario simulation, frontend components, live GitHub ingestion, secure upload parsing, provenance UI, automated tests, production debugging, Vercel Services configuration, deployment, and submission documentation. The human supplied goals, tested behavior, reviewed claims and trade-offs, redirected work, authenticated deployment, and made final release decisions.

## How GPT-5.6 was used

ChatGPT GPT-5.6 Sol contributed extensive research, product framing, critique, scope control, and orchestration before goals were transferred into the primary Codex session. The product also contains a backend-only `gpt-5.6-sol` Responses API provider for evidence-grounded explanations with `store: false`; it falls back deterministically when unavailable. Do not claim production runtime verification until `OPENAI_API_KEY` is configured and the live provider label reads `gpt-5.6`.

## Challenges

- Normalizing very different input formats without executing repository code.
- Providing useful uncertainty when coverage and workflow history are absent.
- Staying under Vercel multipart and Python bundle constraints.
- Packaging read-only fixture assets inside a polyglot Services deployment.
- Keeping optional GitHub/OpenAI failures from blocking core analysis.

## Accomplishments

- One public no-login deployment with live GitHub PR analysis.
- Small Git bundle and ZIP-plus-patch analysis.
- Evidence, confidence, provenance, deterministic baseline, and six scenario comparisons.
- Ground-truth guided fixture and reproducible evaluation.
- Server-side GPT-5.6 provider with honest fallback labelling.

## Lessons learned

Evidence and uncertainty are product features, not caveats. Optional AI should explain traceable outputs, not hide prediction logic. Serverless limits should shape honest input constraints early.

## What is next

Learn a calibrated action-conditioned latent representation of repository and workflow state, using consented historical outcomes and prospective evaluation.

## Submission checklist

- [x] Production URL: https://imerge-ai.vercel.app
- [x] Public repository URL: https://github.com/manasrpandya/PR_consequence_sim
- [ ] Public YouTube demo under three minutes: `ADD URL`
- [ ] Codex `/feedback` session ID: `RUN /feedback IN THE CURRENT CODEX SESSION`
- [x] Category: Developer Tools
- [ ] License: owner name/approved license required
- [ ] Team members: `ADD FINAL DEVPOST NAMES`
- [x] README setup, test, architecture, security, limitations, and AI-use documentation
- [x] AI build log and demo script
- [ ] Configure `OPENAI_API_KEY` and verify the live `gpt-5.6` provider label
