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
- Decision: git worktree per phase (Phase 0-5), branched off main inside this repo, merged after each phase's review gate passes. Coding tasks drafted as prompts (via opencode-prompt skill) and delegated to OpenCode manually; Claude reviews OpenCode's output for correctness against this plan and handles all non-coding reasoning (ground-truth spot-checks, retry/fallback rule design, this log).
- Reasoning: worktrees isolate each phase for clean review/rollback without disturbing main; phases are sequential/dependent so per-phase (not per-task) is the right isolation grain. OpenCode delegation saves Claude Code usage on mechanical implementation while keeping design reasoning and defensibility with Claude.

## What I Tried That Failed
- [Fill in during build — e.g. "tried X threshold for grounding check, broke on Y case because Z, switched to..."]
