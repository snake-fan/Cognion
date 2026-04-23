## Project
Cognion is a full-stack app for processing materials into chat, notes, and knowledge-graph workflows.

## Structured
- `frontend/src/main.jsx`: frontend entry.
- `frontend/src/App.jsx`: root app composition.
- `frontend/src/layout`, `frontend/src/components`, `frontend/src/hooks`, `frontend/src/services/api.js`: UI structure, state hooks, and API client.
- `backend/app/main.py`: FastAPI entry, `/health`, startup DB init, and `/api` router registration.
- `backend/app/routes`: API endpoints for chat, papers, notes, and knowledge graph.
- `backend/app/agents`: agent core, implementations, templates, and orchestration-related logic.
- `backend/app/services`: backend domain services, including knowledge graph services.
- `backend/app/db`: database initialization and persistence layer.
- `backend/test`: backend test suite.
- `docs`, `storage`, `backend/storage`: docs and local/generated data.

## Priorities
1. Correctness
2. Simplicity
3. Consistency with existing code
4. Small diff

## Rules
- Touch only what is needed.
- Follow existing project structure and style.
- Do not introduce new dependencies unless required.
- Do not refactor unless it directly supports the task.
- Clarify the problem and requirements before coding so user intent and implementation understanding are aligned.
- If anything material is uncertain, stop immediately and ask the user instead of guessing and continuing to code.
- After each coding pass, run relevant tests and review the code diff before wrapping up.

## Workflow
1. Clarify the task, requirements, and assumptions before changing code.
2. Locate the relevant files and inspect surrounding code.
3. If any important detail is still uncertain, stop and ask the user.
4. Apply the smallest workable change.
5. Verify related call sites and edge cases.
6. Run relevant tests and review the diff.
7. Summarize the result briefly.

## Response format
- Changed:
- Reason:
- Test Command:
- Diff Review:
- Risk / follow-up:
