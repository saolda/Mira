# Development workflow

- Complete the requested implementation and run appropriate tests.
- Commit completed work to Git.
- ALWAYS push completed commits to the configured GitHub remote.
- Do not consider a task finished until the push succeeds.
- If a push fails, report the error explicitly. Never silently leave
  completed work unpushed.
- In the final response, provide the commit SHA, branch, push status,
  and test results.

## Owner-controlled architecture and prompts

- `architecture.md` and production LLM prompts are controlled by the project owner.
- Never modify them without explicit approval of the proposed changes.
- Discuss proposed changes in the completion report rather than implementing them.
- This restriction overrides general instructions to update documentation or improve prompts.
- Do not silently modify prompt wording while refactoring application code.
