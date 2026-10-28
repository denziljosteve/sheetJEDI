# sheetJEDI — Frontend

React + TypeScript + Vite + Tailwind CSS v4 SPA for sheetJEDI. See the
[root README](../README.md) for setup, architecture, and verification gates.

## Commands

```bash
npm install
npm run dev        # Vite dev server on http://localhost:5173
npm run typecheck  # tsc --noEmit (strict)
npm test           # Vitest + React Testing Library (21 tests)
npm run lint       # oxlint
npm run build      # production build → dist/
npx playwright test  # e2e with /api/v1 fully mocked (no backend needed)
```

## Notes

- API base: `/api/v1` (Vite dev server proxies to `http://127.0.0.1:8000`).
- E2E tests mock the entire API surface in the browser — no backend process,
  no provider keys, no paid calls. Safe for CI.
- Monaco loads from a CDN at runtime with a plain `<pre>` fallback when
  unavailable (see `src/components/workspace/CodeBlock.tsx`).

---

© 2026 Denzil Josteve Fernandes · denziljosteve@gmail.com ·
https://www.linkedin.com/in/denziljosteve/ · https://denziljosteve.github.io/ ·
https://github.com/denziljosteve/
