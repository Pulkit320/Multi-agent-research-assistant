---
trigger: always_on
---

Code style rules for this entire project:
- Prefer explicit, readable code over clever or compressed code. If a one-liner and a
  4-line version do the same thing, write the 4-line version.
- No premature abstraction. Don't build a generic "AgentBase" class or plugin system
  until at least two concrete agents actually need to share behavior — introduce
  shared base classes only when the duplication becomes obvious, not in advance.
- Every agent class and every non-trivial function needs a short docstring explaining
  WHY it exists, not just what it does (the "what" should be clear from the code
  itself).
- Add inline comments only at points a beginner would genuinely get stuck: e.g. why a
  particular prompt instruction is there, why a retry cap is 2 and not something else,
  why two branches run in parallel instead of sequentially.
- Keep functions short and single-purpose. If a function is doing three things,
  split it into three functions with names that say what each one does.
- Use descriptive variable names over short ones (`sub_questions`, not `sq` or `arr`).
- Avoid unnecessary dependencies — if the standard library or a library already in
  the stack can do it, don't add a new package for one function.
- When you introduce a new pattern for the first time (e.g. the first LangGraph node,
  the first conditional edge, the first SSE stream), add a code comment flagging it
  as "first example of X in this codebase" so it's easy to find later.
- Config values (retry counts, model names, timeouts) go in one place (config.py),
  never hardcoded inline in multiple files.