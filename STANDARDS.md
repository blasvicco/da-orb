# Full-Stack Development Standards

This document outlines the standard architecture, technical stack, environment setup, and coding guidelines for our full-stack projects. Use this as the definitive guide for scaffolding, structuring, and writing code in any new or existing project.

## 1. System Architecture & General Structure

Our projects follow a decoupled full-stack architecture, typically divided into a backend API, a frontend client, and a unified infrastructure hub.

### Directory Layout
- `app/`: Contains the main application codebases.
  - `backend/`: The backend API application.
  - `frontend/`: The frontend client application.
- `hub/`: Contains infrastructure configurations, including Dockerfiles for different environments (Node, Python, Message Brokers, etc.).
- `docker-compose.yml`: Main orchestration file for local development.

### Local Environment Services
The standard local development environment is fully dockerized and includes:
- **`backend`**: Backend application API server.
- **`frontend`**: Frontend client development server.
- **`worker`**: Background task processor (e.g., Celery worker).
- **`rabbit`**: Message broker for the task queue.
- **`redis`**: In-memory data store for caching and WebSockets.

---

## 2. Backend Standards

### Tech Stack
- **Framework**: Python with Django + Django REST Framework (DRF)
- **Asynchronous Tasks**: Celery with RabbitMQ
- **WebSockets**: Django Channels + Redis
- **Database**: PostgreSQL (`psycopg2-binary`) or SQLite for local development
- **Notable Libraries**:
  - `drf-standardized-errors`: For consistent API error responses.
  - `django-oauth-toolkit`: For OAuth2 authentication.
  - `django-cors-headers`, `django-filter`, `django-money`

### Backend Project Structure
The backend separates core configuration, REST APIs, and background workers into distinct modules:
- `core/`: Main configuration handling global settings (`settings.py`), middlewares, templates, and base handlers/validators.
- `api/` (or specific app names): The main API application containing:
  - `models/`: Database models.
  - `modules/`: Reusable business logic, viewsets, and domain-specific logic.
  - `resources/`: Serializers or API resources.
  - `validators/`: Data validation logic.
  - `tests/`: Unit and integration tests (`pytest`).
  - `urls.py`: API routing.
- `worker/`: Background task definitions and worker configurations.
- `web_socket/`: Channels and WebSocket consumers.
- `shell/`: Bash scripts for running tests, formatting, and linting code.

### Code Standards & Linting
We strictly enforce code quality using **Black** (for formatting) and **Pylint** (for linting).
Don't add padding anywhere in the code, no in the assignations no either in methods arguments or comments.
Methods declarations, arguments properties or fields, all of them need to follow alphabetically order.
Public methods first, Protected methods second and private methods last.
Protected methods need to have one underscore prefix, private methods need to have two underscore prefix.
Docstrings and comments must be written in English, and they must be written in one line using `"""` enclousure. Argument details or method example comments should use `#` not `"""`.

#### Formatting
- **Formatter**: `black-with-tabs`. We use tabs instead of spaces for indentation.
- **Linter**: `pylint` with the `pylint-django` plugin.
- Shell scripts (e.g., `./shell/do.sh <filename.py>`) are used to run Black and Pylint concurrently.

#### Rules & Naming Conventions
- **Line Length**: Maximum 150 characters.
- **Module Size**: Maximum 1000 lines per module.
- **Indentation**: Tabs (`\t`).
- **Complexity Limits**:
  - Max arguments per function: 5
  - Max branches: 12
  - Max locals: 15
  - Max statements: 50
  - Max returns: 6
- **Variables & Naming Styles**:
  - `snake_case` for Variables, Arguments, Attributes, Functions, Methods, and Modules.
  - `PascalCase` for Classes.
  - `UPPER_CASE` for Constants.
  - Allowed short names: `Run`, `_`.
  - Prohibited bad names: `foo`, `bar`, `baz`, `toto`, `tutu`, `tata`, `i`, `j`, `k`, `err`.
  - Unused or dummy variables must be prefixed with an underscore (e.g., `_unused`, `dummy`).

### Development Workflow
1. **Architecture**: Follow the DRF structure. Keep models simple and place reusable business logic/viewsets in `modules/`.
2. **Formatting**: Always format and lint modified files before committing.
3. **Testing**: Write tests in the respective `tests/` directories using `pytest`.

---

## 3. Frontend Standards

### Tech Stack
- **Framework**: Vue 3 (Composition API) + Vite
- **State Management**: Pinia
- **Routing**: Vue Router
- **Styling**: Tailwind CSS + Ant Design Vue
- **Internationalization (i18n)**: Vue I18n
- **Notable Libraries**:
  - Payment integrations (e.g., `@paypal/paypal-js`, `@stripe/stripe-js`)
  - Date manipulation (`dayjs`)
  - SVG component loading (`vite-svg-loader`)

### Frontend Project Structure
- `src/`
  - `assets/`: Static assets like images and global CSS.
  - `components/`: Reusable, generic UI components.
  - `layouts/`: Base layout structures for pages.
  - `views/`: Page-level components corresponding to routes.
  - `modules/`: Domain-specific logic, composables, or feature-based grouping.
  - `router/`: Vue Router configuration.
  - `i18n/`: Internationalization locales and configuration.
  - `styles/`: Tailwind and global style configurations.
- `vite.config.js`: Vite configuration, including custom plugins (e.g., `dockerEnvPlugin`).
- `eslint.config.js`: ESLint configuration for Vue 3 flat config.
- `components.d.ts`: Auto-generated file for auto-imported components.

### Code Standards & Linting
Code quality is enforced using **ESLint** and **Prettier** (integrated via ESLint plugin).
Don't add padding anywhere in the code, no in the assignations no either in methods arguments or comments.
Methods declarations, arguments properties or fields, all of them need to follow alphabetically order.

#### Rules
- Use the `eslint-plugin-vue` flat recommended configuration for Vue 3.
- **Unused Variables**: `no-unused-vars` is treated as an error. Variables and arguments prefixed with an underscore (e.g., `_val`) are explicitly ignored.
- **Vue Specific Rules**:
  - `vue/attribute-hyphenation`: Disabled (allows camelCase props).
  - `vue/v-on-event-hyphenation`: Disabled (allows camelCase events).
  - `vue/multi-word-component-names`: Disabled (allows single-word component names).
- **Global Variables**: Browser globals are allowed, as well as injected application environments (e.g., `__APP_ENV__`).

#### CSS & Tailwind Standards
- **Style Isolation**: View-specific styles must reside inside the same folder as their corresponding views, using a dedicated `.css` stylesheet (e.g., `src/views/landing.css` for `src/views/landing.vue`).
- **Tailwind v4 Reference**: View-specific stylesheets must import global theme definitions using `@reference "@/styles/main.css";` to access utility configurations natively without duplication.
- **Alphabetical Class Sorting**: All Tailwind utility classes declared inside a CSS `@apply` directive **MUST be sorted alphabetically** (e.g., `@apply cursor-pointer flex gap-3 items-center no-underline;`).

### Development Workflow
- **Linting**: Use linters to check for issues and auto-fix styling errors.
- **Components Auto-importing**: Utilize auto-import plugins (e.g., `unplugin-vue-components`) for UI libraries like Ant Design Vue to simplify templates and reduce manual imports.

---

## 4. Environment Variables & Authentication

### Environment Variables Management
- Backend variables define server behavior, integrations, and database connections.
- Frontend variables are injected via Docker and parsed by a custom Vite plugin (e.g., `dockerEnvPlugin`). These are exposed globally as a constant object (e.g., `__APP_ENV__`). Always prefer using this global object over standard Vite `import.meta.env` if the variable comes from the Docker runtime environment.

### OAuth2 Authentication Setup (DRF + Vue)
We utilize OAuth2 for securing communications between the frontend and backend.
1. **Public API Token**: For endpoints that do not require user credentials.
   - Client type: `public`
   - Grant Type: `client-credentials`
   - Calculate `Base64(client_id:client_secret)` to be used by the frontend client.
2. **Private API Token**: For endpoints requiring user authentication.
   - Client type: `public`
   - Grant Type: `password`
   - Calculate `Base64(client_id:client_secret)` to be used by the frontend client.
