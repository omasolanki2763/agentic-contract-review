# Decisions Log

Format per entry: **Decision** → **Reasoning** → **Alternatives considered / rejected** → **What I'd change if I did it again**

## Domain & Scope
- Decision: NDA-only, CUAD-sourced, presence + deviation-detection (no severity scoring).
- Reasoning: [in your own words — bounded ground truth, no legal background to defend risk judgments]
- Rejected: general multi-tool agent (no coherent ground truth possible across unrelated tasks); data-cleaning automation agent (heavier ground-truth burden than a decision-memo project, and drops the "document" framing entirely); weighted/graded legal-risk scoring (needs legal expertise not held).

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
