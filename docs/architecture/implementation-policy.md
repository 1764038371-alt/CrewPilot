# Implementation Policy

CrewPilot is built MVP-first.

- Keep the Workspace as the product center.
- Prefer working software over expanding design.
- Use Command objects for Workspace edits.
- AI creates proposals; it does not directly rewrite schedule versions.
- Server state belongs in React Query.
- Workspace UI state belongs in Zustand.
- Local pointer and hover interactions stay in component state.

