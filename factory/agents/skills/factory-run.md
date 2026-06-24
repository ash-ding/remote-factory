# /factory-run — CEO Dispatch

Use this skill to launch, monitor, and manage factory CEO runs.

## Dispatch Modes

**Long-running improvement (preferred for multi-project):**
```bash
factory tmux <project_path> --loop
factory tmux <project_path> --loop --interval 1800  # custom interval (seconds)
```
Runs in a detached tmux session. Use this when managing multiple projects — sessions persist and you can check back later.

**Single blocking cycle:**
```bash
factory ceo <project_path>
```
Runs in foreground, blocks until the cycle completes. Use when you want to immediately process results after completion.

**Targeted single-item build:**
```bash
factory ceo <project_path> --focus "<backlog item or issue>"
factory ceo <project_path> --focus 42          # GitHub issue number
factory ceo <project_path> --focus "owner/repo#42"
```

**Mode selection:**
```bash
factory ceo <project_path> --mode improve   # default — score-driven improvement
factory ceo <project_path> --mode design    # brainstorm what to work on first
factory ceo <project_path> --mode research  # research-driven improvement
factory ceo <project_path> --mode meta      # improve the factory itself + ACE evolution
```

## Monitor Running Sessions

```bash
factory tmux-ls
```
Lists all active factory tmux sessions with project paths and status.

## Stop a Session

```bash
factory tmux-stop --session <session_name>
factory tmux-stop --path <project_path>
```

## Check Results After Completion

1. Read `.factory/reviews/ceo-latest.md` in the project directory for the CEO's final output
2. Run `factory eval <project_path>` for the current composite score
3. Run `factory history <project_path>` for the full experiment log
4. Read `.factory/reviews/` for individual agent outputs (builder-latest.md, qa-latest.md, etc.)

## When to Use Which

| Scenario | Command |
|---|---|
| Managing 2+ projects simultaneously | `factory tmux <path> --loop` for each |
| User asks "work on this project" | `factory tmux <path> --loop` |
| User asks to build one specific thing | `factory ceo <path> --focus "<item>"` |
| User wants to discuss what to work on | `factory ceo <path> --mode design` |
| Quick one-off improvement | `factory ceo <path>` |

Always check `factory tmux-ls` before dispatching to avoid launching duplicate sessions for the same project.
