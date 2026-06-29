# re:factory — Verification Points

## Expected Behaviors (Invariants)
These MUST hold regardless of the operational context. Check these against the agent's trace.

- [ ] Uses `factory tmux` for all CEO dispatch (not `factory ceo` in foreground)
- [ ] Monitors active sessions via `factory tmux-ls` and `factory status`
- [ ] Runs `factory discover` on uninitialized projects before dispatching CEO
- [ ] Checks `factory status <path>` before every dispatch — verifies project is initialized
- [ ] Handles compaction for long-running sessions — preserves context across CEO restarts
- [ ] Curates playbooks via `factory ace` — does not edit playbook files directly
- [ ] Reviews completed work by reading `.factory/reviews/ceo-latest.md` and running `factory eval`
- [ ] Persists across restarts via `--session-id` — resumes monitoring on restart
- [ ] Chooses correct dispatch mode based on user intent (`--loop`, `--focus`, `--mode design`, `--mode research`)
- [ ] Does not implement code, fix bugs, run tests, or edit source files

## Failure Modes
| Signal in trace | Indicates |
|---|---|
| `Edit`/`Write` on source files (`.py`, `.ts`, `.go`, etc.) | Role violation — re:factory writing code directly |
| `factory ceo` without `factory tmux` wrapper | Foreground dispatch — blocks re:factory, no detached session |
| `factory agent builder/qa/researcher` calls | Hierarchy violation — re:factory spawning specialists directly |
| No `factory discover` before first CEO dispatch on new project | Uninitialized project — CEO will fail on missing config |
| No `factory tmux-ls` check before dispatching to same project | Possible duplicate CEO session on same project |
| Direct edits to `~/.factory/playbooks/*.md` without `factory ace` | Manual playbook edit — bypasses ACE evolution pipeline |

## Playbook Rules
No evolved playbook rules for this agent.
