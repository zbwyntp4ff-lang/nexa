# NEXA AI - Frontend
**Think. Create. Act.**
This is NEXA AI's web frontend - a Next.js (App Router) + TypeScript +
Tailwind CSS + shadcn/ui application. It is a **separate app** from the
Python/FastAPI backend (`../app`): it never holds any provider API keys and
talks to the backend exclusively over HTTP.
## Stack
- **Next.js 16** (App Router, Turbopack) + **TypeScript** + **Tailwind CSS v4**
- **shadcn/ui** (Base UI primitives) for accessible building blocks (Dialog,
  Sheet, Tabs, Tooltip, Dropdown Menu, ...)
- **Zustand** (+ `persist`) for client state: chat history, projects, theme,
  and transient UI state - all stored in this browser's `localStorage`
- **next-themes** for Light / Dark / System theming
- **react-markdown** + **remark-gfm** + **rehype-highlight** for chat
  rendering (tables, lists, links, images, syntax-highlighted code blocks)
- **Vitest** + **React Testing Library** for unit/component tests
- **Playwright** for the end-to-end test
## Running locally
```bash
npm install
cp .env.example .env.local     # point NEXT_PUBLIC_API_BASE_URL at your backend
npm run dev -- -p 4820         # http://localhost:4820
```
The backend (see `../README.md`) must be running for Chat/Agent/Code modes
to actually respond - by default at `http://localhost:8420` with
`AI_PROVIDER=mock`, so no API keys are required to try it out.
> Access the dev server via the **same hostname** you started it with
> (e.g. `localhost`, not `127.0.0.1`) - Next.js 16 blocks cross-origin
> requests to its dev assets by default. This is already relaxed in
> `next.config.ts` (`allowedDevOrigins`) for `localhost`/`127.0.0.1`/`0.0.0.0`.
## Scripts
| Command | What it does |
|---|---|
| `npm run dev` | Start the dev server |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint |
| `npm run test` | Unit/component tests (Vitest) |
| `npm run test:watch` | Unit tests in watch mode |
| `npm run e2e` | End-to-end tests (Playwright; starts its own dev server) |
## Project structure
```
src/
├── app/                     # Next.js App Router entry (layout, page, globals.css)
├── components/
│   ├── ui/                  # shadcn/ui primitives
│   ├── common/              # Logo
│   ├── theme/                 # ThemeProvider, ThemeToggle
│   ├── layout/                 # AppShell, Header, Sidebar (+ mobile drawer)
│   ├── chat/                   # Conversation, Message, Composer, ModeSelector,
│   │                             StatusIndicator, MarkdownMessage, ToolResultList,
│   │                             EmptyState, ComingSoonBanner
│   ├── projects/                # ProjectPanel (conversations/files/memory/instructions)
│   └── settings/                 # SettingsDialog + 7 sections
├── hooks/                    # useConversationController, useBackendHealth, useMediaQuery
├── lib/                      # api.ts (backend client), types.ts, attachments.ts
├── store/                    # chat-store.ts, ui-store.ts (Zustand)
└── test/                     # Vitest unit/component tests
e2e/                          # Playwright end-to-end tests
```
## What's real vs. "Coming Soon"
Only **Chat**, **Agent**, and **Code** modes are wired to the backend
(`POST /api/v1/chat` and `POST /api/v1/agent`). **Research**, **Create**, and
**Vision** modes show a "Coming Soon" panel instead of simulating a response -
see the root `README.md` for the full breakdown of what's implemented on the
backend for each of those (Part 3) versus what has an HTTP endpoint today.
Voice input (STT) is not implemented server-side yet either - clicking the
mic button shows a toast saying so, rather than pretending to record.
## Desktop app (Part 8.5)
This same frontend also ships as a desktop app via Electron - see
`electron/` and the "Part 8.5" section in `../README.md` for the full
architecture. Quick commands:
```bash
npm run electron              # run the desktop shell against `npm run dev` (port 4820)
npm run dist:electron:linux   # build a real AppImage (bundles this build's own .venv)
npm run dist:electron:win     # build the Windows NSIS installer + portable .exe
```
