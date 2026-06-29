# Skill Reviewer — Verification Points

## Expected Behaviors (Invariants)
These MUST hold regardless of the operational context. Check these against the agent's trace.

- [ ] Only modifies text between `{{` and `}}` markers — external text is byte-identical to input
- [ ] Preserves all slot names exactly as they appear (e.g., `timeout_<id>`, `task_prompt_<id>`)
- [ ] Returns the complete markdown document — no truncation or omission
- [ ] Timeout values are calibrated to agent role (Builder: 1200-1800s, QA: 1800s, Researcher: 600s, Archivist: 300s)
- [ ] Task prompts reference specific artifacts the agent should read (from annotation context)
- [ ] Task prompts include context about what upstream agents produced
- [ ] Gate prompts have concrete pass/fail criteria, not vague assessments
- [ ] Failure actions include specific recovery instructions (revert, close PR, finalize as error)
- [ ] Finalize commands use shell variables (`$EXP_ID`, `$VERDICT`, `$HYPOTHESIS`) not literal placeholders
- [ ] Does not add or remove any `<!-- -->` annotation comments
- [ ] Does not add or remove any slot markers

## Failure Modes
| Signal in trace | Indicates |
|---|---|
| Diff shows changes outside `{{` and `}}` markers | External text modification — structural corruption of skill template |
| Slot names changed (e.g., `timeout_build` → `timeout_builder`) | Slot name mutation — downstream template processing will break |
| Output truncated or missing sections from input | Incomplete output — skill file will be corrupted |
| Timeout values identical to defaults with no justification | No improvement made — review was a no-op |
| Task prompts lack artifact references despite annotation context available | Missed enrichment opportunity — agents get generic instructions |
| Gate prompts use vague language ("check if good", "review output") | Weak gate criteria — CEO gates become rubber stamps |

## Playbook Rules
No evolved playbook rules for this agent.
