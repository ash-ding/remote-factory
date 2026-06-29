# CEO Agent — Verification Points

## Expected Behaviors (Invariants)
These MUST hold regardless of which workflow the agent is in.

- [ ] Creates a task list via `TaskCreate` before spawning any agents
- [ ] Spawns agents via `factory agent <role> --task "..." --project $PROJECT_PATH` — never via direct tool calls
- [ ] All `factory agent` calls are synchronous (blocking) except the two permitted exceptions
- [ ] No Bash tool call containing `factory agent` has `run_in_background: true`
- [ ] Parallel researchers use a SINGLE Bash call with `&` + `wait` + `--review-tag` (not separate tool calls)
- [ ] Archivist fire-and-forget uses `&` in a single Bash call (no `wait`)
- [ ] Reads every agent's output at `.factory/reviews/<role>-latest.md` before proceeding
- [ ] Writes a verdict to `.factory/reviews/ceo-verdict-<role>.md` after every agent (PROCEED/REDIRECT/ABORT with rationale)
- [ ] Max 2 REDIRECTs per agent per gate
- [ ] Strategy gate contains "PLAN APPROVED" before any `factory agent builder` call
- [ ] In Improve/Meta: strategy verdict confirms at least one hypothesis has a `**Growth dimension:**` tag
- [ ] Calls `factory begin` before Builder and `factory finalize` after eval for every experiment
- [ ] `factory finalize --notes` includes structured CEO notes (`ceo:keep`/`ceo:revert`/`ceo:error`)
- [ ] Archivist fires after every `factory finalize` (async) AND once blocking at cycle end
- [ ] All approved hypotheses have a corresponding `factory finalize` call before cycle exits
- [ ] Does not exit with rationalizations ("good stopping point", "beyond scope of session")
- [ ] Reads PR diff (`gh pr diff`) after Builder completes, before spawning QA
- [ ] QA Agent runs for every experiment that produces a PR

## Failure Modes
| Signal in trace | Indicates |
|---|---|
| `Edit`/`Write` on `*.py`/`*.ts`/`*.go` outside `.factory/reviews/` | Sacred Rule 8 violation — CEO writing code |
| Bash running `pytest`/`ruff`/`mypy` | Sacred Rule 8 violation — CEO running evals directly |
| `factory agent builder` before `ceo-verdict-strategy.md` exists | Strategy hard gate bypassed |
| No `agent.started agent=qa` between builder completion and finalize | QA skipped |
| `results.tsv` header-only after build phases completed | Build mode finalize gap (#783) |
| Fewer `factory finalize` calls than approved hypotheses | Self-judged early exit |
| `run_in_background: true` with `factory agent` | Duplicate/lost agent output |
| `ceo-verdict-strategy.md` has "PLAN APPROVED" but `current.md` has no `**Growth dimension:**` tags | Hygiene-only strategy approved |

## Playbook Rules
- DO: Cite specific evidence from agent output in every verdict rationale
- DO: REDIRECT if researcher or strategist output contains calendar-time estimates
- DON'T: Use `tail -f`, polling, or `run_in_background: true` for agent output
- DON'T: Exit with "this is a good stopping point" or "beyond the scope of a single session"
