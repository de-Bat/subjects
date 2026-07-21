# Claude Code setup reflection

Diagnosis only — no changes made. Based on 4 subagents scanning ~65 session transcripts across ~20 project directories under `~/.claude/projects/`. Ranked most leverage first (recurrence × fix simplicity, weighed against build cost).

---

## 1. No project-level CLAUDE.md anywhere — highest leverage, near-zero build cost

**Finding:** Global `~/.claude/CLAUDE.md` has only graphify/caveman triggers + email/date — zero engineering conventions. **Not one** of the ~20 project directories scanned (subjects, interior-dash, TaskbarGroups, rosetta, gardens, gardens2-0, i-dash, AFont, VTextStudio, strata, serenity-plusplus, myToWatch, contestr, AVid, audio-il, wingroup, jolly-bell) has a project CLAUDE.md. Every session re-derives stack, build/test commands, known bugs, and environment quirks from scratch.

**Evidence:**
- interior-dash: identical bug report (plan-scanner mismatches, room coloring, commit-on-rejection) retyped near-verbatim across two sessions (`a46ce22a`, `f8cdaa84`), each preceded by `/clear` — no persisted known-issues list.
- TaskbarGroups: AHK gotchas (uninitialized-var warning, `Gui has no window`/`WinRedraw` crash, popup monitor-coordinate quirks) recur across 3+ sessions with no record.
- rosetta/gardens: hard-won debugging knowledge (exe-lock-on-rebuild, D2D/InvalidateRect paint-timing bug) not captured; `pyinstaller` PATH issue and `requirements-desktop.txt`/`desktop.spec` edits rediscovered.
- misc batch: 8+ projects (subjects, strata-build, contestr, audio-il, AVid, serenity-plusplus...) all start sessions with large upfront "you are an expert X engineer, mission, locked decisions" prompts that a CLAUDE.md would shrink to a reference.
- Missing deps discovered live and undocumented: `gcc`/cgo (strata-build), `pdftoppm`, `pypdf` (AFont).

**Verdict: fix.** Not a skill — just populate CLAUDE.md per active project (stack, build/test commands, known bugs/quirks, env deps). Cheapest, broadest-impact item on this list. Prioritize interior-dash, TaskbarGroups, rosetta, gardens/gardens2-0 — they have the most sessions and the clearest recurring rediscovery cost.

---

## 2. Kill/relaunch/rebuild dev-loop repeated by hand across 4 different projects

**Finding:** Same shape of pain — "build or process is stuck/locked, kill it, relaunch, re-observe" — recurs across unrelated tech stacks, each time hand-typed fresh.

**Evidence:**
- TaskbarGroups (`f475232a`): `taskkill //F //IM AutoHotkey64.exe` + relaunch, **22 invocations in one session**, including a wrong-flag-syntax failure first (`taskkill /F` → "Invalid argument/option").
- interior-dash: port-in-use on dev server start was painful enough that the user opened a **dedicated worktree** (`fix-port-1420`) to fix it, then separately asked to "apply same fixes to tauri" — cross-session, cross-surface recurrence.
- gardens (`0602591e`): `Access is denied (os error 5)` on release build because the built exe was still running → `Stop-Process` + rebuild, rediagnosed rather than known.
- gardens2-0 (`b515ef3f`, `5b59711a`, ~1900 lines combined): build → kill process → relaunch → screenshot cycle for a native Win32 app, with the **same hand-written PowerShell `Add-Type` C#/P-Invoke window-capture snippet re-authored 40+ times**.

**Verdict: automation, per-project.** Not one universal skill (AHK/PowerShell, Rust/cargo, Tauri, Win32 P-Invoke are different enough), but each of these 4 projects would benefit from a small saved script/skill: "stop stale process, rebuild, relaunch, capture window" as one command instead of reconstructed by hand. The gardens2-0 case (40+ reauthored P-Invoke screenshot boilerplate) is the single highest raw-waste item found — worth a `run`-skill-style helper first.

---

## 3. `/deep-research` invoked 4 times, always failed — cheapest concrete fix

**Finding:** gardens2-0: user typed `/deep` or `/deep-research` in 4 separate sessions (`a5087686`, `047c8bbe`, `eaeb1060`, +1) intending a research-then-plan workflow for a home-design app idea. Every time: `Unknown command`. Each of those sessions is only 7-11 lines — the actual request was never executed, four times over.

**Verdict: build a skill/slash-command.** Clear, repeated, named-by-habit expectation with a well-defined shape (web research → implementation plan). Small build cost, direct fix for a request that has failed 4/4 times.

---

## 4. Untracked runtime-state file causes repeated manual git reasoning

**Finding:** rosetta: `backend/settings.json` (runtime state, not gitignored) shows up modified in `git status` in 26 instances across 3 sessions, requiring Claude to manually reason each time about excluding it from commits.

**Verdict: fix.** One `.gitignore` line in rosetta. Trivial cost, eliminates a recurring (if small) tax on every commit in that project.

---

## 5. No canonical test/typecheck invocation documented — candidate for CLAUDE.md + possibly a hook

**Finding:** rosetta: `npx tsc --noEmit` run 90+ times after edits, almost always from `web/`. pytest invoked ad hoc with inconsistent flags (`-q -p no:randomly` vs plain) 20+ times — no canonical script exists, so the invocation is re-guessed each session. gardens: `Get-Process gardens | Stop-Process -Force` + `cargo build --release` repeats verbatim every rebuild.

**Verdict: fix (CLAUDE.md) now, automation (PostToolUse hook) only if it keeps recurring after that.** Documenting the exact command removes the re-guessing; a hook to auto-run tsc after edits is a reasonable follow-up but higher build cost for a smaller marginal gain once the command itself is known.

---

## 6. "Keep going, don't stop for check-ins" + progress-file habit repeated across sessions

**Finding:** interior-dash: user had to explicitly say "continue through all tasks, don't stop for check-ins" in at least 2 sessions (`093939f4`, `d97cf66e`), and separately asked for a progress-ledger update in 4+ sessions (`89ed5e71`, `95af749c`, `d97cf66e`, `a46ce22a`, `f8cdaa84`) — a manual snapshot-before-context-runs-out ritual, repeated every time rather than automatic.

**Verdict: fix (CLAUDE.md default) + reminder to actually invoke `planning-with-files`.** The `planning-with-files` skill already does exactly this (task_plan.md/progress.md), but transcripts show it wasn't being reached for in these sessions. A CLAUDE.md line ("default to running multi-task work to completion without pausing for check-ins unless blocked") plus a nudge to use the existing skill covers this without building anything new.

---

## 7. Windows path/tool friction: Bash backslash mangling, inconsistent Bash/PowerShell choice, habitual `cd`

**Finding:** `cd C:UsersRonDownloads: No such file or directory` (AFont) — Windows backslash paths breaking in the POSIX Bash tool. 258 Bash vs 209 PowerShell tool calls across sessions suggests inconsistent tool selection for path-heavy work. `cd` used as the first token in a Bash/PowerShell call 158 times, despite existing tool guidance to avoid this and use absolute paths directly.

**Verdict: nothing to build — this is a standing-instruction adherence gap, not a missing tool.** Already covered by tool-level guidance ("avoid `cd`," "match syntax to the tool"); worth a feedback-memory note for future sessions to actively self-correct on, not a new skill or config change.

---

## 8. Everything else checked — no action warranted

- **Worktree friction** (subjects: file-lock on `.claude/worktrees/...` cleanup; strata-build: `EnterWorktree` guard errors, `TaskUpdate` schema errors) — each was a one-off that the agent adapted to within the same session. Not recurring enough across projects to justify a fix yet; monitor.
- **Permission/tool-denial friction** — searched explicitly across all 4 batches; found in only 2-3 sessions total (mild over-exploration cut short by the user), and zero explicit permission-denial strings in TaskbarGroups, interior-dash, or the rosetta/gardens batch. Not a real pattern.
- **Typos in user messages** (TaskbarGroups) — Claude handles these fine; not friction.
- **Superpowers workflow usage** (brainstorming → writing-plans → subagent-driven-development → finishing-a-development-branch) — already the de facto default across many projects; working as intended.

---

## Summary ranking

| # | Cluster | Recurrence | Verdict |
|---|---|---|---|
| 1 | No project CLAUDE.md | ~20 projects, universal | Fix — populate per active project |
| 2 | Manual kill/relaunch/rebuild loop | 4 projects, up to 40+ reauthored boilerplate in one | Automation — small per-project helper scripts |
| 3 | `/deep-research` missing | 4/4 failed attempts, 1 project | Build a skill/slash-command |
| 4 | Untracked `backend/settings.json` | 26 occurrences, 1 project | Fix — `.gitignore` line |
| 5 | No canonical test/typecheck command | 90+ / 20+ occurrences, 1 project | Fix (CLAUDE.md), automate later if needed |
| 6 | "Don't pause for check-ins" + progress file | 2 + 4 sessions, 1 project | Fix (CLAUDE.md default + use existing skill) |
| 7 | Windows path/tool friction | 258/209 tool calls, cross-project | Nothing to build — adherence gap |
| 8 | Worktree/permission edge cases | 1-2 sessions each | Nothing — monitor |
