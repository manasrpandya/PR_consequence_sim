# Demo video script (target 2:45)

Record after warming one live PR analysis in a spare tab. Keep the guided example ready as backup; do not wait on GitHub during the final take.

## 0:00–0:20 — Problem

**Screen:** Production homepage, hero visible. **Narration:** “A pull request changes more than lines. It can reach dependent modules, invalidate tests, increase engineering risk, and slow the path to green—but teams rarely see those technical and workflow consequences together before merge.”

## 0:20–0:35 — Product

**Clicks:** Slowly point to the five output cards. **Narration:** “PR Consequence Simulator turns one proposed change into five decisions: impact, relevant tests, transparent risk, workflow delay, and the safest next action—with evidence and uncertainty attached.”

## 0:35–1:40 — Live judge-testable analysis

**Screen/clicks:** In Public PR, paste the preselected unseen URL; click **Inspect input**, then **Analyze change**. During real progress, narrate once; use the warmed result tab if the request takes over eight seconds. Scroll through Observed, Predicted, risk factors, Suggested, explanation, and provenance.

**Narration:** “No account is required. This is a real public GitHub PR, not the fixture. The backend loads bounded PR metadata and patches and never executes repository code. Here are observed facts and provenance. The deterministic engine traces likely impact, ranks structural tests, exposes every risk contribution, and labels confidence. Workflow timing is shown only when supported. Then six interventions are compared so the recommendation is explicit. GPT-5.6 explains this supplied evidence and cites evidence identifiers; it does not invent these numbers. The provider label also makes fallback behavior visible.”

**Backup:** If GitHub is unavailable, click **Example**, select the high-complexity migration, and say: “I’m using the prepared ground-truth path because GitHub is temporarily unavailable; judges can still paste any public PR.”

## 1:40–2:10 — Technical implementation

**Screen:** README architecture diagram, then briefly show `services/engine/app/uploads.py`, `service.py`, `explanations.py`, and tests. **Narration:** “A Next.js frontend and Python FastAPI backend deploy together through Vercel Services. GitHub and uploads normalize into one evidence model. Deterministic impact, test, risk, workflow, and scenario components remain inspectable. Uploads are size-bounded, filtered, request-scoped, and never executed. The fixture evaluation and automated tests keep claims reproducible.”

## 2:10–2:35 — Codex and GPT-5.6

**Screen:** README ‘Built with’ table or `docs/ai-build-log.md`. **Narration:** “ChatGPT GPT-5.6 Sol performed extensive research, ideation, critical review, and orchestration. I transferred those goals into the primary Codex session, where Codex with GPT-5.6 implemented most of the code, tests, integrations, hardening, and deployment. I stayed in the loop, tested the product, reviewed trade-offs, and redirected development. GPT-5.6 also runs in the product for evidence-grounded explanations when configured.”

## 2:35–2:50 — Closing

**Screen:** Return to homepage with URL bar visible. **Narration:** “PR Consequence Simulator gives engineers one evidence-backed view of what a change may affect and what to do next—before merge. Try it now at pr-consequence-simulator.vercel.app.”
