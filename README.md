# Orb

**Orb** is a conversational platform that gives everyone in your organization one place to get things done — across every tool, system, and process you already use.

---

## The problem

Modern organizations run on dozens of tools: ERP systems, CRMs, ticketing platforms, procurement tools, HR portals, and more. Each one has its own interface, its own terminology, and its own learning curve.

Employees waste time switching between systems, looking up how to do things, and waiting on specialists who know the tools well enough to operate them. Onboarding takes longer than it should. Processes that should take minutes take hours — not because the work is hard, but because the tools are.

---

## What Orb does

Orb sits in front of all those tools and gives users a single, natural language interface to access and trigger any process in the organization.

Instead of logging into different platforms and navigating their menus, users simply describe what they need. Orb understands the intent, figures out which system and process to use, collects whatever information is required through a guided conversation, and executes the action — all in one place.

A typical interaction looks like this:

> **User:** I need to open a support ticket for a client who can't log in.
>
> **Orb:** Sure. What's the client's name or account?
>
> **User:** Acme Corp, contact is John.
>
> **Orb:** Got it. How urgent is this?
>
> **User:** High priority, they're blocked.
>
> **Orb:** Here's the ticket I'll create in Jira: *[summary]*. Should I submit it?

The underlying system — whether it's Jira, SAP, Salesforce, or an internal API — is invisible to the user. They just get things done.

---

## Key features

- **One interface for everything** — A single chat window replaces navigating multiple platforms. If the process exists in your organization, Orb can reach it.
- **Natural language understanding** — Users describe what they need in their own words. Orb identifies the right process automatically.
- **Guided data collection** — Orb asks only what it needs, in the right order, so nothing gets missed and nothing has to be filled out twice.
- **Safe execution** — Every action is reviewed and confirmed before anything is submitted. Users stay in control at all times.
- **Full conversation history** — Chats are saved so users can revisit past operations, resume incomplete ones, or audit what was done and when.
- **Multi-language support** — Available in English and Spanish, with more languages easy to add.
- **Expertise levels** — Users can choose how much context Orb provides, from step-by-step explanations for newcomers to concise summaries for power users.
- **Light and dark mode** — A clean, modern interface that feels comfortable for everyday use.
- **Multi-tenant** — Each organization gets its own fully isolated environment, with its own tool connections and configurations.

---

## Who it's for

- **Employees** who need to trigger processes across systems they don't use often enough to memorize.
- **Teams** with repetitive, cross-system workflows — operations, finance, HR, support, logistics — who want to move faster without more training.
- **Organizations** that want to reduce the cost of onboarding, eliminate tool-switching friction, and make institutional knowledge accessible to everyone.

---

## How it works (without the jargon)

1. A user opens Orb and describes what they need in plain language.
2. Orb's AI understands the request and identifies which organizational process applies.
3. Orb has a focused conversation to collect all the required information.
4. The user reviews a clear summary and confirms.
5. Orb executes the action in the right system and reports back.

Behind the scenes, each process is defined through configuration — not custom code — so new tools and workflows can be connected quickly as the organization grows and changes.

---

---

## Technical details

### Architecture

```
User Browser
    ↓
Vue 3 SPA  (Landing page + Chat UI)
    ↓
REST API + WebSocket
    ↓
Django Backend (DRF + Django Channels)
    ↓
PostgreSQL  (Sessions, messages, org config)
    ↓
n8n Workflow Engine  (Orbot — core orchestration logic)
    ↓
Claude LLM  (Intent classification, guided collection, execution)
    ↓
Connected Tools & Systems  (SAP, CRMs, ticketing, internal APIs, ...)
```

### Tech stack

**Backend**

| Layer | Technology |
|---|---|
| Framework | Django 5.1 + Django REST Framework |
| Real-time | Django Channels + Redis (WebSockets) |
| ASGI server | Daphne |
| Database | PostgreSQL + psycopg2 |
| Orchestration | n8n (main, webhook, worker) |
| Encryption | Fernet (symmetric, for org config) |
| Auth | OAuth2 / OpenID Connect |

**Frontend**

| Layer | Technology |
|---|---|
| Framework | Vue 3 (Composition API) |
| Build tool | Vite |
| State | Pinia |
| Routing | Vue Router 4 |
| UI library | Ant Design Vue 4 |
| Styling | Tailwind CSS v4 |
| i18n | Vue I18n 11 |

**Infrastructure**

| Service | Role |
|---|---|
| `backend` | Django API (port 8000) |
| `frontend` | Vite dev server (port 5173) |
| `postgres` | Primary database (port 5432) |
| `redis` | Cache + WebSocket broker (port 6379) |
| `n8n-main` | Workflow editor (port 5678) |
| `n8n-webhook` | Webhook receiver (port 5679) |
| `n8n-worker` | Background execution |
| `github-mcp` | GitHub MCP server (port 3000) |

### Key concepts

- **Multi-tenancy** — Organizations are isolated by slug, each with their own encrypted integration configs and tool connections.
- **Session model** — Each chat session maps to a user + org combination, with full message history stored in PostgreSQL.
- **Orchestration engine** — The core bot logic (intent routing, guided data collection, tool calls) runs as an n8n workflow (`Orbot v3.json`), making it auditable and modifiable without touching application code.
- **Configuration-driven processes** — Organizational processes are defined as configuration, not code, so new tools and workflows can be onboarded without a deployment.
- **WebSocket streaming** — Agent responses stream in real time over Django Channels, giving users immediate feedback during longer operations.

### Code quality

- **Backend**: Black formatter (tabs), Pylint, max 150-character lines.
- **Frontend**: ESLint flat config, Prettier, auto component imports.
- **Testing**: pytest (backend), vitest-ready (frontend).
- **Language**: English-only for all code comments and docstrings.

### Environment variables

Key configuration is managed through environment variables:

| Variable | Purpose |
|---|---|
| `POSTGRES_*` | Database connection |
| `SECRET_KEY` | Django secret key |
| `FIELD_ENCRYPTION_KEY` | Fernet key for org config encryption |
| `REDIS_HOST` | Redis for caching and WebSockets |
| `N8N_CALLBACK_SECRET` | Webhook verification for n8n |
| `GITHUB_*` | GitHub API access for MCP integration |
