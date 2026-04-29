# OMKA Frontend

**Generated:** 2026-04-29 14:47 | **Commit:** c36c4b8 | **Branch:** main

## Overview

React 19 SPA with TypeScript, Vite 8, Tailwind CSS, and shadcn/ui patterns. Communicates with FastAPI backend via REST API.

## Structure

```
frontend/src/
├── api/            # API client + typed endpoint functions
├── components/
│   ├── layout/     # AppShell, AppSidebar, PageHeader
│   ├── cards/      # Domain-specific card components
│   ├── common/     # Shared components
│   └── ui/         # shadcn/ui primitives
├── hooks/          # Custom hooks (use-sources, use-candidates, etc.)
├── lib/            # Utilities (cn.ts for className merging)
├── pages/          # Route-level page components
├── styles/         # globals.css (Tailwind directives)
└── types/          # TypeScript type definitions
```

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| Add new page | `pages/` + `App.tsx` | Add route in App.tsx |
| Add API endpoint | `api/` | Follow `client.ts` pattern |
| Add data hook | `hooks/` | Follow `use-sources.ts` pattern |
| Add UI component | `components/ui/` | Use shadcn/ui patterns |
| Add layout change | `components/layout/` | Modify AppShell/AppSidebar |
| Change API base URL | `api/client.ts` | Also update `vite.config.ts` proxy |

## Conventions

### Component Pattern

```tsx
// Functional components with explicit props interface
interface MyComponentProps {
  title: string
  onSelect?: (id: string) => void
}

export function MyComponent({ title, onSelect }: MyComponentProps) {
  return <div className={cn("base-styles", conditional && "extra")}>...</div>
}
```

### Hook Pattern

```tsx
// Custom hooks manage state + API calls
export function useMyData() {
  const [data, setData] = useState<MyType[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await myApi.getAll()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  return { data, loading, error, refetch: fetchData }
}
```

### API Client Pattern

```tsx
// Typed API functions in api/ directory
import { api } from "./client"

export interface MyType { id: string; name: string }
export interface CreateMyTypeRequest { name: string }

export const myApi = {
  getAll: () => api.get<MyType[]>("/my-endpoint"),
  create: (data: CreateMyTypeRequest) => api.post<MyType>("/my-endpoint", data),
  delete: (id: string) => api.delete(`/my-endpoint/${id}`),
}
```

### Styling Pattern

```tsx
// Tailwind + cn() utility for conditional classes
import { cn } from "@/lib/cn"

<div className={cn(
  "base-styles",
  isActive && "active-styles",
  variant === "primary" ? "primary-styles" : "secondary-styles"
)}>
```

## Anti-Patterns

- **Never** use `className` string concatenation. Use `cn()` from `@/lib/cn`.
- **Never** fetch data directly in components. Use custom hooks.
- **Never** hardcode API URLs. Use `api/client.ts` + Vite proxy.
- **Never** use `any` type. Define proper interfaces.
- **Never** add business logic to pages. Pages compose components + hooks.

## Commands

```bash
# Dev
npm run dev          # Start dev server (port 5173)
npm run build        # Type check + production build
npm run lint         # Run ESLint

# Preview
npm run preview      # Preview production build
```

## Notes

- Vite dev server proxies `/settings`, `/sources`, `/candidates`, `/digests`, `/knowledge` to `http://127.0.0.1:8000`.
- Path alias `@` maps to `./src` (configured in `vite.config.ts`).
- shadcn/ui components use `class-variance-authority` for variants + `clsx` + `tailwind-merge`.
- All pages are wrapped in `AppShell` which provides sidebar + main content layout.
- Error handling: hooks catch errors and expose `error` string; components display via toast/alert.

## Known Issues

- **Empty directories:** `components/cards/`, `components/common/`, `components/ui/`, `types/` are empty (scaffolded but not populated)
- **API client bypasses proxy:** `api/client.ts` hardcodes `http://127.0.0.1:8000` instead of using Vite proxy
- **No test framework:** No vitest, jest, or testing-library configured
- **No `test` script:** `package.json` has no test command
