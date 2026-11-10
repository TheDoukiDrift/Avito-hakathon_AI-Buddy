# AI-buddy — frontend

React 18 + TypeScript + Vite, Zustand, TanStack Query, Zod.

```bash
corepack pnpm install     # или pnpm install
corepack pnpm dev         # http://localhost:5173, /api проксируется на localhost:8000
corepack pnpm build       # tsc --noEmit + vite build
corepack pnpm test        # Vitest
corepack pnpm coverage    # покрытие по слоям api/stores/utils
```

Демо-доступы: `intern@example.com`, `mentor@example.com`, `manager@example.com`,
`hr.bp@example.com`; пароль `test1234`.

Docker: `frontend/Dockerfile` собирает статику и отдаёт её через nginx
(`frontend/nginx.conf`: SPA-fallback, прокси `/api/` на `http://backend:8000`
с выключенной буферизацией для SSE).
