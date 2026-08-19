# Decisions Log

Format per entry: **Decision** → **Reasoning** → **Alternatives considered / rejected** → **What I'd change if I did it again**

## Domain & Scope
- Decision: Distributor-Agreement-only, CUAD-sourced, presence + deviation-detection (no severity scoring). Pivoted from the originally-planned NDA domain in Phase 0.
- Reasoning: [in your own words — bounded ground truth, no legal background to defend risk judgments]
- Pivot detail: CUAD's 510 contracts are organized into 25 documented business-relationship types (Distributor, License, Franchise, Consulting, Joint Venture, Supply, etc.) — NDA is not one of them. Verified directly, not assumed: searched all 510 titles + lawyer-labeled "Document Name" answers for NDA/confidentiality keywords, found 2 loose hits, neither an actual NDA. Considered building NDAs from an unlabeled source instead (e.g. scraping SEC EDGAR the way CUAD's own scrape.py does) but rejected — that would mean hand-building the entire ground truth with no lawyer labels to derive it from, which breaks the 1-week timeline and the whole point of using an expert-annotated dataset. Picked Distributor Agreement over the runner-up, License Agreement, using measured clause coverage, not doc count alone: License has more docs (36 vs 31) but Distributor wins on 4 of the 5 checklist categories that appear in both — Non-Compete (42% vs 20%), Termination-for-Convenience (42% vs 34%), Cap-on-Liability (68% vs 59%), Anti-Assignment (81% vs 76%); License only wins on IP Ownership Assignment (29% vs 10%), which was dropped from the checklist anyway (see below).
- Rejected: general multi-tool agent (no coherent ground truth possible across unrelated tasks); data-cleaning automation agent (heavier ground-truth burden than a decision-memo project, and drops the "document" framing entirely); weighted/graded legal-risk scoring (needs legal expertise not held).

## Corpus Cleaning
- Decision: excluded 2 of the 31 CUAD Distributor Agreement entries — both are amendment riders to an already-executed agreement (`NETGEAR,INC...AMENDMENT TO THE DISTRIBUTOR AGREEMENT...`, `NEONSYSTEMSINC...DISTRIBUTOR AGREEMENT_Amendment`), not standalone contracts. Working corpus is **29 documents**.
- Reasoning: an amendment document typically only contains the specific clause(s) being modified. Grading it against the full 8-category checklist would record most categories as "absent" not because the underlying deal actually lacks them, but because the amendment PDF never restates them — a labeling artifact, not a real signal. Caught by inspecting per-document checklist-clause counts during dev/validation split construction (amendments stood out as extreme low-count outliers, e.g. 1/8, alongside a same-company "_New" full-agreement counterpart at 6/8).
- Impact: dev set stays 20 docs; full-validation set shrinks from 11 to 9 (29 − 20). Noted as a further, smaller-than-planned validation set, on top of the earlier NDA→Distributor pivot shrinkage.

## Checklist Categories
- Decision: 8 categories — Governing Law, Non-Compete, Termination for Convenience, Cap on Liability, Uncapped Liability, Anti-Assignment, Exclusivity, License Grant.
- Reasoning: measured presence rate across the clean 29-doc CUAD Distributor Agreement corpus (2 amendment-only riders excluded — see "Corpus Cleaning" above) for every one of CUAD's 41 clause categories (not guessed). Kept the 6 categories from the original NDA-oriented checklist that still had reasonable coverage in this domain (Governing Law 97%, Non-Compete 45%, Termination-for-Convenience 45%, Cap-on-Liability 72%, Uncapped-Liability 24%, Anti-Assignment 83%). Dropped No-Solicit-of-Employees and IP Ownership Assignment — both near-absent (~5-10% on the pre-cleaning corpus), expected since neither is core to a distributor relationship. Replaced with Exclusivity (66%) and License Grant (79%) — both central to what a distributor agreement actually negotiates (exclusive vs. non-exclusive territory, what's being licensed to distribute). Uncapped Liability is kept despite thin coverage (24%) deliberately — it's a paired red-flag category with Cap on Liability (absence-of-a-cap is the interesting/rare finding, not something to optimize away for a higher coverage number).
- Rejected: keeping the original NDA-oriented 8 unchanged (would ship 2 checklist items that almost never fire in this domain, weakening the whole "X of Y clauses present" signal); swapping Uncapped Liability for a higher-coverage category — considered, but would lose the deliberate Cap/Uncapped-Liability paired-flag design carried over from the original plan.

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

## Workflow
- Decision: git worktree per phase (Phase 0-5), branched off main inside this repo, merged after each phase's review gate passes.
- Decision: task split between Claude and OpenCode is by stakes, not by "coding vs. non-coding." Claude keeps: all answer-key construction (Phase 0 dev-set + full-validation-set answer keys — the ground truth everything else is graded against), all core pipeline/design logic, and every simple/small task. OpenCode gets only genuinely irrelevant/mechanical/boilerplate tasks — nothing load-bearing for accuracy or defensibility. Every OpenCode prompt must explicitly require OpenCode to explain its reasoning ("why this, why that") for each choice it makes; Claude reviews that explanation against this plan before accepting the output.
- Reasoning: worktrees isolate each phase for clean review/rollback without disturbing main; phases are sequential/dependent so per-phase (not per-task) is the right isolation grain. Answer keys are the foundation the 90% accuracy target and the whole regression suite are measured against — if that's wrong, everything built on top of it is wrong too, so it can't be delegated. Forcing OpenCode to explain its reasoning turns its output into something Claude can actually audit, instead of a black box to trust or not.

## What I Tried That Failed
- [Fill in during build — e.g. "tried X threshold for grounding check, broke on Y case because Z, switched to..."]
