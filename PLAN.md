# Portfolio Project Plan: Agentic Contract Clause-Review Pipeline with Full Observability

## Context

Portfolio project for ML/GenAI + data-science entry-level roles (India, fresher, prepping for job search + master's applications simultaneously). Built by a fresher who is still learning core Python, using Claude Code as the implementation tool, with a hard rule: every phase gets reviewed and understood before the next one starts, because the entire point of the project is being able to defend every design choice out loud in a technical interview — a working demo that can't be explained is worth nothing.

**What actually gets built:** an agent that reads a contract (PDF), checks it against a fixed checklist of legal clause types, and produces a decision memo — but the memo itself is explicitly the *boring* part. The differentiator is everything wrapped around it: traced execution, token/cost accounting, a real retry/timeout/fallback policy with documented reasoning per threshold, and a regression suite over a hand-inspected ground-truth set that catches silent breakage when a prompt changes.

**Domain pivot (Phase 0 finding, verified not assumed):** originally scoped as NDA-only. Verifying CUAD in Phase 0 found CUAD organizes its 510 contracts into 25 documented business-relationship types, and **NDA is not one of them** — a keyword/document-name search across all 510 lawyer-labeled contracts found essentially zero true NDAs (2 loose keyword hits, neither an actual NDA). Rather than hand-build an NDA ground truth from an unlabeled source (which would have blown the 1-week budget and the whole point of using an expert-labeled dataset), the domain pivoted to **Distributor Agreement** — CUAD's real type with the best clause-checklist fit (see the "Domain & Scope" decision in DECISIONS.md for the full comparison against License Agreements, the runner-up). The project was renamed `agentic-contract-review` accordingly — general enough to not misrepresent the actual domain, and to fit the ideal-version goal of pluggable multi-type support.

---

## Scope (v1) vs. Ideal Version vs. Explicit Non-Goals

### v1 scope (buildable in ~1 week at current Python level)
- **Domain:** legal contract review, **Distributor Agreement contract type only** (pivoted from NDA in Phase 0 — see Context above and DECISIONS.md).
- **Data source:** CUAD (Contract Understanding Atticus Dataset) — free, public, 510 real commercial contracts with lawyer-applied clause labels across 41 categories, organized into 25 documented contract types. Distributor Agreement is one of those 25 types: **31 documents**, confirmed by direct count in Phase 0.
- **Clause checklist:** 8 CUAD categories, finalized against real coverage data measured in Phase 0 (not guessed): **Governing Law (94%), Non-Compete (42%), Termination for Convenience (42%), Cap on Liability (68%), Uncapped Liability (23%), Anti-Assignment (81%), Exclusivity (68%), License Grant (74%)** — percentages are presence rate across the 31 Distributor Agreement docs. Two categories from the original NDA-oriented list (No-Solicit of Employees, IP Ownership Assignment) were dropped after Phase 0 measurement showed they're nearly absent in this domain (6% and 10% respectively) and replaced with Exclusivity and License Grant, both core to distributor deals.
- **Per-clause output:** Present/Absent, exact quoted text (grounded — verified to actually exist in the source), location, occurrence count, and a binary **Matches-standard / Deviates-from-standard** flag (comparison against a reference clause text derived from CUAD's own corpus — not a legal-risk judgment, just a text-similarity detection the human reader interprets themselves).
- **Document summary line:** simple completeness count ("X of Y checklist clauses found present") — no weighted score, no Compliant/Flagged/Non-compliant verdict label.
- **PDF parsing:** pdfplumber first; a lightweight heuristic (extracted-text-length vs. page count, garbage-character ratio) detects failure; OCR/LLM extraction only runs as a fallback if the heuristic flags a problem.
- **Failure handling / fallback chain:** Gemini (primary) → Groq (AI fallback, different provider) → rule-based regex/keyword fallback (last resort, always produces *something*). Output is flagged when a fallback tier was used.
- **Orchestration:** hand-written plain Python — no agent framework in v1.
- **Tracing:** Langfuse (free tier), used standalone via its SDK, independent of orchestration choice.
- **Ground truth — two-stage:** (1) a **dev set of 20 documents**, spot-checked (3-5+ personally read against source), used continuously during Phases 1-4 as the fast regression suite re-run after every prompt tweak; (2) a **full-set answer key covering the remaining 11 Distributor Agreement contracts in CUAD** (31 total − 20 dev = 11), built mechanically at the same time as the dev set (cheap, no reason to delay), but not run against the pipeline until it's passing well on the dev set — then run once as a broader final validation pass, catching cases the dev set never specifically debugged against. Both answer keys built mechanically from CUAD's existing labels. (The full-validation set is thinner than originally assumed — 11 docs, not "dozens" — a direct consequence of the domain pivot; still useful as an overfitting check, just weaker statistically than hoped.)
- **Metrics:** clause-level accuracy AND document-level accuracy, reported together. Target **90%** on both — a practical bar, not 100% (chasing perfection on a small/derived eval set risks silently tuning prompts to the eval set itself rather than generalizing).
- **Speed:** no invented number up front — measure real happy-path latency once the pipeline runs, then optimize down as far as practical. Retry/fallback-triggered runs are allowed to take longer than the happy path; that's an accepted reliability trade-off, not a bug.
- **Cost tracking:** token counts logged on every run from day one (cheap, always-on). Whether to build a cost-reporting/dashboard *feature* on top of the logs is decided near the end of the build, based on remaining time.

### Explicit non-goals for v1 (cut deliberately, not by oversight — say so if asked)
- No multi-contract-type support (Distributor Agreement only; other types are a checklist swap away, not built).
- No severity/risk grading of a clause deviation — binary flag only, no "how bad" judgment, because that requires legal expertise not held.
- No weighted/aggregate compliance verdict (no "Compliant/Flagged/Non-compliant" label) — same reason.
- No semantic/embedding-based matching anywhere (grounding check or reference comparison) — fuzzy string matching only. Cheaper, faster, and avoids an unjustifiable similarity threshold.
- No LangGraph or any agent framework in v1 — deferred deliberately to a post-v1 migration exercise (see below), specifically so the framework's abstractions aren't being learned under the same time pressure as Python fundamentals and the core logic.
- No local-model (Ollama) fallback tier, no OpenRouter tier — collapsed to one AI fallback (Groq) + rule-based, to fit the 1-week budget. (A 5-tier cascade was seriously considered and cut — see DECISIONS.md.)
- No guaranteed cost-dashboard UI — token logging yes, presentation layer is a stretch goal decided late.
- No partial-credit/graded clause scoring — binary only.

### Ideal version (documented now, built later — real interview talking points, not vaporware)
- Multiple contract types via pluggable per-type checklists, merged into one system (module-per-contract-type, shared engine).
- Expanded fallback cascade: add OpenRouter and/or a local model (Ollama, feasible on the available RTX 3060 / Ryzen 9 6800HX) as additional independent failure domains.
- LangGraph migration of the hand-written v1 pipeline — done deliberately as a learning + before/after comparison exercise once the hand-written version is fully understood, not rushed into v1.
- Graded/partial-credit clause scoring with a properly researched rubric (needs legal-domain reading that wasn't in scope for v1).
- Cost-dashboard / reporting UI, if not already built in v1's Phase 5.
- Richer deviation detection (beyond corpus-derived reference-text comparison) if accuracy demands it.

---

## Architecture

```
PDF (Distributor Agreement)
  │
  ▼
[1] PDF Text Extraction
    pdfplumber (primary) → heuristic failure check → OCR/LLM fallback (rare)
  │
  ▼
[2] Clause Extraction  (LLM: Gemini primary)
    For each checklist clause type: Present/Absent, quoted text, location, count
    Grounding check: fuzzy-match quoted text against source (catches hallucination)
  │  (failure) → retry/fallback chain, see Failure Handling below
  ▼
[3] Reference Comparison  (deterministic, no LLM)
    Compare quoted text vs. CUAD-corpus-derived reference text per clause type
    → Matches-standard / Deviates-from-standard (binary, no severity judgment)
  │
  ▼
[4] Decision Memo Assembly
    Per-clause structured result + "X of Y clauses present" summary line
  │
  ▼
Output (JSON/markdown memo) + Langfuse trace (spans, latency, tokens, retries, fallback-used flag)
```

Steps [1] and [2] are the only steps that call an external LLM/API and therefore the only steps with retry/fallback logic. Step [3] is plain Python (fast, free, no failure surface worth handling). Step [4] is formatting.

---

## Every Parameter, Value, and Reason

| Parameter | v1 Value | Reason |
|---|---|---|
| Contract type | Distributor Agreement only (pivoted from NDA — CUAD has no NDA type) | Bounds ground truth and checklist to one coherent domain; avoids "does this clause even apply to this contract type" ambiguity. Distributor Agreement chosen over the runner-up (License Agreement, 36 docs) because measured checklist-clause coverage is stronger across the board — see DECISIONS.md. |
| Clause checklist size | 8 categories | Common/high-value Distributor Agreement clauses, each with measured presence-rate ≥23% in the actual data; explicitly disclosed as non-exhaustive rather than pretending completeness — standard practice in real legal-tech scoping. |
| Per-clause scoring | Binary (Present/Absent) + binary (Matches/Deviates standard) | Avoids needing legal judgment to grade "how broken" a clause is; still concretely useful since the actual clause text is shown for the human to judge. |
| Clause weighting | None (simple completeness count) | A weighted/aggregate score needs defensible per-clause weights, which needs legal expertise not held; a plain count needs none. |
| Reference clause source | Derived from CUAD's own corpus (most common phrasing per category) | Fully data-driven, no external legal research needed, defensible as a factual dataset claim rather than a legal opinion. |
| PDF parser | pdfplumber, primary | Free, simple, sufficient for CUAD's clean text-based PDFs; matches the free-tier/no-budget constraint. |
| PDF fallback trigger | Heuristic: extracted-text-length vs. page count, garbage-character ratio | Detects failure without needing to run (and pay for) the LLM path on every document just to compare. |
| Grounding-check method | Fuzzy string match | Tolerant of whitespace/formatting noise; a verbatim-presence check doesn't need semantic/embedding matching, and embeddings add latency the speed goal doesn't allow. |
| Timeout per API call | 3× measured average call latency | Empirical, not guessed — measured from real early test calls, avoids an arbitrary constant. |
| Retry: network/timeout/per-minute rate limit (429) | Retry ×2, exponential backoff | Transient by nature — likely to succeed on retry; exponential backoff specifically clears a per-minute rate-limit window instead of hammering it. |
| Retry: malformed output (invalid JSON/schema) | Retry ×1, with a corrective re-prompt | A nudge usually fixes formatting slips; more than one retry on a pure format issue is wasted. |
| Retry: grounding-check failure (hallucinated clause) | No retry — skip straight to AI fallback | Retrying the identical prompt on the identical document tends to reproduce the identical hallucination; a different model is more likely to help than asking the same one again. |
| Retry: daily quota exhausted (429 quota-type, distinct from per-minute) | No retry — skip straight to fallback | Waiting within the same day doesn't fix a quota that's actually finished; must distinguish this from the per-minute 429 case by reading the error response. |
| Fallback chain | Gemini → Groq → rule-based regex | 3 tiers, not 5 — Groq and OpenRouter together were redundant (both cloud, similar independence gain); local Ollama dropped due to uncertain output quality; rule-based kept as the one tier with near-zero failure surface, guaranteeing the pipeline never returns nothing. |
| Orchestration | Hand-written Python | Full transparency for defensibility at current Python level; the custom fallback/retry logic doesn't map cleanly onto a generic framework's abstractions anyway. |
| Tracing tool | Langfuse | Purpose-built, free tier, professional-standard tool (using it is normal practice, not "not really building it yourself" — same category as using pytest or Grafana). |
| Accuracy target | 90%, both clause-level and document-level | Practical bar; 100% on a small/derived eval set risks overfitting prompts to the eval set rather than generalizing. |
| Ground truth set size | Two-stage: 20-doc dev set (fast iteration) + 11-doc full-validation set (all remaining CUAD Distributor Agreements, run once dev set passes) | More data is better once reading-time is no longer the bottleneck, but a full-size set re-run after every single prompt tweak would be too slow — splitting into a fast dev loop plus a broader final check gets both speed and coverage. 11 is thinner than originally hoped (a consequence of the domain pivot — CUAD has 31 Distributor Agreements total, not "dozens to hundreds"), but still a genuine held-out check. |

---

## Ground-Truth Labelling Protocol

1. **Pull CUAD, filter to Distributor Agreement contracts.** Done: 31 of 510 CUAD contracts match (identified by title/document-name; CUAD has no separate type field, so type is inferred from the lawyer-labeled "Document Name" answer and filename). Confirmed by direct count, not assumed — the original NDA assumption was checked in Phase 0 and found to be wrong (CUAD has zero true NDAs among its 25 documented types); see Context and DECISIONS.md.
2. **Build two answer keys mechanically, at the same time.** CUAD's labels already exist in machine-readable form; Claude (not OpenCode — this is the ground truth everything downstream is graded against) formats them into structured per-document answer-key files (clause type → present/absent, location, quoted span) for the chosen 8-category checklist — one covering a **20-document dev subset**, one covering the **remaining 11 Distributor Agreement contracts** (the full-validation set). Both are built together since it's pure data reformatting either way, not judgment — safe to automate, no reason to delay building the larger one.
3. **Spot-check, don't blindly trust.** Personally read 3-5+ of the assembled dev-set answer-key entries against the actual source documents — pick a mix (at least one clause-rich document, at least one with several absent clauses) rather than 3 similar-looking ones. The goal isn't auditing CUAD's legal correctness (trust the lawyers) — it's personally understanding *why* each label is what it is, so any of it can be explained live under interviewer questioning.
4. **Document the trust boundary explicitly.** In DECISIONS.md, record exactly which documents were spot-checked and state plainly that the remaining labels (across both the dev set and the full-validation set) are trusted as-is from CUAD's published, expert-verified dataset (cite CUAD's own reported label-quality/inter-annotator-agreement stats as the justification for not re-verifying every row — this is standard practice when using a trusted external benchmark, not a shortcut).
5. **Derive reference clause text** for the Matches/Deviates-standard check from the same CUAD Distributor Agreement subset — the most common phrasing pattern per clause category.
6. **Use the two sets differently going forward:** the 20-doc dev set is the one re-run constantly (Phases 1-4, after every prompt tweak); the full-validation set is run once, near the end of Phase 4, after the dev set is passing near target — a broader check against documents never individually debugged against.

---

## What Gets Measured, and How

- **Clause-level accuracy** = % of (document × clause-type) pairs where the pipeline's Present/Absent call matches the ground-truth answer key. Fine-grained, shows precision on the core extraction task.
- **Document-level accuracy** = % of documents where the full per-document checklist result matches the ground truth (exact-match definition to be finalized in Phase 4 — e.g. all clause calls correct vs. some tolerance).
- Both are computed automatically by the **regression suite**: a pytest-based script that runs a ground-truth document set through the live pipeline and diffs the output against the answer key, on demand.
- **Two-stage suite, matching the two-stage ground truth**: the **dev suite** (20 docs) is run after every prompt/logic change during Phases 1-4 — fast enough (target: a couple minutes) to re-run constantly. The **full-validation suite** (remaining 11 CUAD Distributor Agreements) is run once the dev suite is passing near the 90% target, as a broader final check — this doubles as the held-out-style generalization check (see risk below), since those documents were never individually debugged against.
- **Regression suite purpose**: catch silent breakage. Every time a prompt or extraction logic changes, re-run the dev suite — if a document that used to pass now fails, that's caught in minutes, not discovered weeks later. This is the core "instrumentation" deliverable the whole project is built to demonstrate.
- **Token/latency/fallback metadata** per run is captured via Langfuse spans — not a pass/fail metric, but the evidence trail for cost and reliability claims made about the system.
- **Overfitting risk, addressed by the two-stage design**: repeatedly tuning prompts against the same fixed 20-doc dev set risks a reported accuracy number that doesn't generalize. The full-validation set run acts as the check on this — if dev-set accuracy is 90%+ but full-validation accuracy is much lower, that's a real signal of overfitting to the dev set, worth investigating before calling v1 done.

---

## Build Order (Phases)

Matches the collaboration model already agreed: each phase gets built, reviewed, and understood before the next one starts — no phase begins until the previous one's design decisions can be explained back, not just observed working.

**Phase 0 — Setup & Ground-Truth Foundation**
Pull CUAD → confirm domain viability (done: NDA not viable, pivoted to Distributor Agreement, 31 docs) → build both answer keys mechanically (20-doc dev set + 11-doc full-validation set) → spot-check 3-5+ dev-set docs → derive reference clause text per category → finalize the 8-category checklist against measured data (done: swapped No-Solicit-of-Employees/IP-Ownership-Assignment for Exclusivity/License-Grant).
*Deliverable:* two answer-key files (dev + full-validation) + reference-clause file + confirmed checklist.

**Phase 1 — Core Pipeline (happy path only)**
PDF extraction → clause extraction (Gemini, grounding check) → reference comparison → memo assembly. No retries, no fallback, no tracing yet — just prove the shape works on 2-3 sample documents.
*Deliverable:* working end-to-end pipeline, happy path only.

**Phase 2 — Failure Handling & Fallback Chain**
Measure real latency → set timeouts → implement the four retry-by-failure-type rules → exponential backoff → Groq AI-fallback tier → rule-based fallback tier → fallback-used flag in output.
*Deliverable:* pipeline survives induced failures (bad API key, malformed prompt, simulated rate-limit) without ever crashing or returning nothing.

**Phase 3 — Observability**
Integrate Langfuse (span per step, latency, token counts, retry count, fallback tier used). Add token-count logging.
*Deliverable:* every run produces a fully inspectable trace.

**Phase 4 — Regression Suite & Metrics**
Build the pytest-based regression suite against the 20-doc dev set. Compute clause-level and document-level accuracy. Iterate on prompts toward the 90% target, re-running the dev suite after every change to catch regressions. Once dev-set accuracy is near target, run the full-validation suite once as a broader final check (and overfitting sanity check — compare dev vs. full-validation accuracy).
*Deliverable:* one command that runs the dev suite (fast, constant use) and a second that runs the full-validation suite (final check), each reporting both accuracy numbers.

**Phase 5 — Polish & Documentation**
Decide on the cost-dashboard feature (time-permitting). Finalize DECISIONS.md. Write a README (architecture, how to run, how to read output). Record a demo run, including one that deliberately exercises the fallback chain.
*Deliverable:* portfolio-ready repo.

**Phase 6+ (post-v1, "week 2+") — Ideal-Version Upgrades**
LangGraph migration (as its own reviewed mini-project, not a rushed bolt-on) → additional contract types → expanded fallback cascade (OpenRouter/local Ollama) → graded clause scoring → cost dashboard if deferred.

---

## Risks Most Likely to Sink This

1. **Python fundamentals gap under time pressure.** The single biggest risk flagged throughout scoping — basic Python level plus a 1-week timeline. Mitigated by the phase-by-phase review commitment and by keeping v1 scope as minimal as this plan's non-goals list enforces. Don't relitigate cut scope mid-build.
2. **Scope creep.** Already happened repeatedly during scoping itself (data-cleaning pivot, 5-tier fallback cascade, weighted legal-risk scoring, semantic matching everywhere) — all caught and cut before build started. The non-goals list exists specifically so these don't quietly creep back in during implementation.
3. **Free-tier rate limits stalling iteration.** Gemini/Groq free tiers cap requests per minute and per day. A regression suite that's too large, or too much manual re-testing during debugging, can genuinely stall progress for hours. Keep the full suite re-run under a couple minutes; always distinguish per-minute rate-limit 429s (retry-worthy) from daily-quota-exhausted 429s (not retry-worthy).
4. **Ground-truth defensibility gap.** If the answer key is built entirely by Claude Code and never genuinely reviewed, the most likely interview question ("how do you know your ground truth is correct?") has a weak answer. The spot-check step in Phase 0 is not optional — it's the highest-leverage hour in the whole project for defensibility.
5. **Rushed framework migration undoing v1's defensibility.** The week-2+ LangGraph migration risks becoming a shortcut bolt-on that isn't actually understood, which would undercut the very thing the hand-written v1 was built to demonstrate. Treat it as its own reviewed phase, not a footnote.
6. **Overfitting the regression suite.** Repeatedly tuning prompts against the same fixed small eval set can produce an accuracy number that looks good but doesn't generalize. Mitigated by the two-stage ground-truth design — the full-validation set (never individually debugged against) acts as the generalization check once the dev set hits target.

---

## DECISIONS.md Template (create in Phase 0, keep updated throughout)

```markdown
# Decisions Log

Format per entry: **Decision** → **Reasoning** → **Alternatives considered / rejected** → **What I'd change if I did it again**

## Domain & Scope
- Decision: Distributor-Agreement-only (pivoted from originally-planned NDA), CUAD-sourced, presence + deviation-detection (no severity scoring).
- Reasoning: [in your own words — bounded ground truth, no legal background to defend risk judgments; why the pivot happened — CUAD verified to have zero true NDAs among its 25 documented contract types, found in Phase 0 by direct keyword/label search across all 510 docs, not assumed]
- Rejected: NDA (verified non-viable — not a CUAD type); License Agreement as the pivot target (36 docs, more than Distributor's 31, but weaker measured coverage on the checklist: IP Ownership Assignment was the only category it beat Distributor on, 29% vs 10%, while Distributor won on Non-Compete 42% vs 20%, Termination-for-Convenience 42% vs 34%, Cap-on-Liability 68% vs 59%, Anti-Assignment 81% vs 76%); general multi-tool agent (no coherent ground truth possible across unrelated tasks); data-cleaning automation agent (heavier ground-truth burden than a decision-memo project, and drops the "document" framing entirely); weighted/graded legal-risk scoring (needs legal expertise not held).

## Failure Handling
- Decision: 4 distinct retry/fallback rules by failure type; 3-tier fallback chain (Gemini → Groq → rule-based).
- Reasoning: [why per-minute rate limits and daily quota exhaustion need different handling; why grounding failures skip straight to fallback]
- Rejected: 5-tier cascade (Gemini → Groq → OpenRouter → local Ollama → rule-based) — cut for 1-week time budget, documented as an ideal-version extension instead.

## Orchestration & Tooling
- Decision: hand-written Python for v1, LangGraph migration deferred to a dedicated post-v1 phase; Langfuse for tracing regardless of orchestration choice.
- Reasoning: [defensibility given current Python level; framework abstractions vs. custom fallback logic]

## Ground Truth
- Decision: mechanically-built answer key from CUAD, personally spot-checked (list which documents), rest trusted as expert-verified.
- Reasoning: [why spot-checking is standard practice, not a shortcut; why full manual verification doesn't scale]

## What I Tried That Failed
- [Fill in during build — e.g. "tried X threshold for grounding check, broke on Y case because Z, switched to..."]
```

---

## Verification

Once phases are built, "does it work" is verified by:
1. Running the regression suite (Phase 4 deliverable) and confirming both accuracy numbers meet or approach the 90% target, with every failure traceable via Langfuse to a specific step/clause.
2. Deliberately breaking a dependency (e.g. temporarily invalidating the Gemini key) and confirming the pipeline degrades through the fallback chain instead of crashing, with the output clearly flagged as fallback-derived.
3. Re-running the regression suite after a deliberate prompt change and confirming it catches the regression (this is the core "instrumentation" claim of the whole project — worth demonstrating on camera for the portfolio, not just claiming).
