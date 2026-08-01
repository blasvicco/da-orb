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
  - Allowed short names: `Run`, `ex`, `_`.
  - Single-character identifiers are prohibited for variables, arguments, and loop/comprehension variables — use a descriptive name instead. The sole exception is `_` for an intentionally unused value.
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

## 4. Testing Standards

> **All test code must follow the same coding standards as application code** (formatting, naming conventions, linting, line length, complexity limits, import ordering, etc.). Tests are first-class code.

---

### 4.1 Backend Testing Standards

#### Tech Stack
- **Test Runner**: `pytest` + `pytest-django`
- **Factories**: `factory_boy` (`DjangoModelFactory`, or plain `factory.Factory` for non-DB classes) + `pytest-factoryboy` for fixture registration
- **Mocking**: `unittest.mock` + `pytest-mock` (`mocker` fixture) + `monkeypatch`
- **API Client**: `rest_framework.test.APIClient`
- **Reporting**: `allure-pytest` for structured step reporting

#### Test File Location
Test files mirror the source tree under each app's `tests/` directory. Factories live alongside tests in a dedicated `factories/` subdirectory:

```
<app>/tests/
├── conftest.py                     # Fixtures and factory registration for the app
├── factories/                      # DjangoModelFactory / factory.Factory classes (F-prefix naming)
│   ├── organization.py             # FOrganization
│   └── seat.py                     # FSeat
├── middleware/
│   └── organization_test.py        # mirrors <app>/middleware/
├── models/
│   └── organization_test.py        # mirrors <app>/models/
├── resources/
│   └── chat/
│       ├── permission_test.py
│       ├── serializer_test.py
│       └── view_test.py            # mirrors <app>/resources/chat/
└── validators/
    └── seat_exists_test.py         # mirrors <app>/validators/
```

#### pytest Configuration
Each backend app defines its test scope in `pytest.ini`:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = core.settings
python_files = *_test.py
testpaths = core/tests drf_api/tests web_socket/tests
```

#### Test File Structure

Every test file **must** follow this section order:

```python
"""Module docstring describing what is tested"""

# General imports
from contextlib import nullcontext

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.validators import VSeatExists

pytestmark = pytest.mark.django_db  # module-level DB mark when needed


@pytest.mark.parametrize(
    "status, valid",
    [
        ("active", True),
        ("revoked", False),
    ],
)
def test_feature_scenario(status, valid):
    """Plain English description of what the test verifies"""

    with step("Arrange: <description>."):
        context = nullcontext() if valid else pytest.raises(ValidationError)

    with step("Act: Call the function under test."):
        with context as excinfo:
            result = VSeatExists()(org, "bob")

    with step("Assert: Outcome matches expected."):
        assert result is not None if valid else isinstance(excinfo.value, ValidationError)
```

#### Section Rules

| Section | Rule |
|---|---|
| `"""Docstring"""` | Every module and test function must have a docstring. |
| `# General imports` | Standard library only (`json`, `datetime`, `contextlib`, etc.) |
| `# Lib imports` | Third-party packages (`pytest`, `allure`, `factory`, etc.) |
| `# App imports` | Project modules (`drf_api.validators`, `core.models`, etc.) |
| `pytestmark` | Declare `pytest.mark.django_db` at module level when all tests in the file need DB access. Use the decorator per-function otherwise. |

#### Arrange / Act / Assert with Allure Steps

All test functions must structure their body using `allure.step` context managers following the AAA pattern:

```python
with step("Arrange: <what is set up>."):
    ...

with step("Act: <what is called>."):
    ...

with step("Assert: <what is verified>."):
    assert ...
```

This is mandatory — it makes test reports readable and enforces the AAA structure.

#### Parametrization — Default to `@pytest.mark.parametrize`

**Always prefer `@pytest.mark.parametrize` over multiple test functions that repeat the same assertion logic.**

```python
# ✅ Preferred
@pytest.mark.parametrize(
    "payload",
    [
        {"description": "active seat exists", "status": "active", "expected": True},
        {"description": "revoked seat exists", "status": "revoked", "expected": False},
    ],
)
def test_has_active_seat(payload):
    """Test has_active_seat only returns True for a row with status='active'"""
    with step(f"Arrange: {payload['description']}."):
        ...

    with step("Act: Call has_active_seat."):
        result = has_active_seat(org, "bob")

    with step("Assert: Result matches expected."):
        assert result is payload["expected"]


# ❌ Avoid
def test_has_active_seat_when_active(): ...
def test_has_active_seat_when_revoked(): ...
```

Rules:
- Use `@pytest.mark.parametrize` whenever **2 or more** cases share the same assertion structure.
- Use a `payload` dict with a `"description"` key for complex cases; use flat positional args for simple ones.
- Pass `payload["description"]` into the first `with step("Arrange: ...")` label for self-documenting Allure output.

#### Factories

- Factory classes for persisted Django models use `DjangoModelFactory` from `factory.django`; factories for plain (non-DB) classes such as `MSession` use `factory.Factory` directly.
- Factory class names are prefixed with `F` (e.g., `FOrganization`, `FSeat`, `FSession`).
- Factories are registered in `conftest.py` using `pytest_factoryboy.register()`. This generates two fixtures per factory: `f_<name>` (the factory class itself — call `.create()`/`.build()` on it) and `m_<model_name>` (an auto-created model instance), where `<name>`/`<model_name>` are the `snake_case` forms of the factory/model class names.
- Use `factory.Faker`, `factory.LazyAttribute`/`factory.LazyFunction`, `factory.Sequence`, and `factory.SubFactory` for realistic defaults.

```python
# factories/seat.py
class FSeat(DjangoModelFactory):
    """Factory for MSeat"""

    class Meta:
        model = MSeat

    org = factory.SubFactory(FOrganization)
    status = "active"
    username = factory.Faker("user_name")

# conftest.py
from pytest_factoryboy import register
from drf_api.tests.factories import FSeat

register(FSeat)  # → injects f_seat (factory class) and m_seat (auto-created instance) fixtures
```

#### Fixtures and conftest.py

- Place **global fixtures** (shared across all apps) in the root `conftest.py`.
- Place **app-scoped fixtures** in `<app>/tests/conftest.py`.
- Place **sub-feature fixtures** in nested `conftest.py` files when a feature's setup is only relevant to one subtree.
- Autouse fixtures in the root `conftest.py` are used to globally mock heavy side-effects (n8n REST calls, outbound SAP B1S/OpenID HTTP calls) so they never fire during tests.
- Use `scope="session"` only for fixtures that are truly read-only and safe to share across the whole session (e.g., `api_client`).

#### Mocking

- Use `mocker` (from `pytest-mock`) for patching within a test or fixture.
- Use `monkeypatch` for attribute/environment overrides that require precise teardown.
- Use `unittest.mock.MagicMock` and `patch` directly when constructing complex mock objects or using `with patch(...)` context managers.
- Prefer patching at the **import site** of the symbol being tested (e.g., patch `drf_api.resources.auth.driver.b1s.requests.post`, not `requests.post`).

#### API Testing

- Use `rest_framework.test.APIClient` for all HTTP-level tests.
- Use `django.urls.reverse` to build URLs — never hardcode URL strings.
- Org resolution comes from the request's `Host` header (`MOrganizationMiddleware` reads its first label as the org slug), so tests targeting an org-scoped endpoint must set `client.defaults["HTTP_HOST"] = f"{org.slug}.<domain>"` rather than relying on `force_authenticate`.
- Identity (as opposed to org) is resolved per-viewset by the org's configured auth driver — via the `X-SAP-Username`/`X-SAP-Connection-Key` headers for `open_id`, or a verified opaque `Authorization: Bearer <token>` (an `MSessionProxy` row) for `b1s`. Build the header set that matches the permission class under test rather than assuming a single universal "authenticated client" shape.
- `BasePermission`'s own default (`request.user.is_superuser`) is Django-session-authenticated, so use `client.force_authenticate(user=f_user.create())` with `is_superuser=True` only for endpoints that fall back to that default.

#### Naming Conventions
- Test files: `*_test.py` (enforced by `pytest.ini`).
- Test functions: `test_<feature>_<scenario>` using `snake_case`, plain English (e.g., `test_has_active_seat`, `test_resolve_identity_from_bearer_token`).
- Factory classes: `F<ModelName>` (e.g., `FOrganization`, `FSeat`, `FSession`).
- Factory-class fixtures injected by `pytest_factoryboy`: `f_<name>` (e.g., `f_organization`, `f_seat`); auto-created model-instance fixtures: `m_<model_name>` (e.g., `m_organization`).
- Fixture names: `snake_case`, descriptive (e.g., `api_client`).

---

### 4.2 Frontend Testing Standards

#### Tech Stack
- **Test Runner**: Vitest (native Vite integration, zero-config)
- **Component Mounting**: `@vue/test-utils`
- **DOM Environment**: `happy-dom`
- **E2E**: Playwright, all backend HTTP/WebSocket calls mocked (`page.route()` / `page.routeWebSocket()`) — no live backend/n8n needed

#### Test File Location
All test files live under `src/tests/`, mirroring the source tree exactly:
```
src/tests/
├── setup.js                        # Global setup (fetch/WebSocket mocks, localStorage reset)
├── helpers/
│   └── mount.js                    # mount()/shallowMount() wrapper (i18n + router stubs pre-injected)
├── modules/
│   └── websocket/chat.test.js      # mirrors src/modules/websocket/chat.js
├── components/
│   └── chat/bubble.test.js         # mirrors src/components/chat/bubble.vue
└── e2e/
    ├── signin.spec.js
    └── helpers/
        └── mockWebSocket.js
```

#### Test File Structure

Every test file **must** follow this section order:

```js
// Libs imports
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mocks (hoisted by Vitest before any import — affects all App imports below)
vi.mock('@/modules/api', () => ({ default: { Auth: { login: vi.fn() } } }));

// App imports
import AppAPI from '@/modules/api';
import { useAuth } from '@/modules/auth';

// Fixtures
const FIXTURE = { field: 'value' };
const makeFixture = (overrides = {}) => ({ ...FIXTURE, ...overrides });

describe('ModuleName.methodName', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each([
    ['case A description', inputA, expectedA],
    ['case B description', inputB, expectedB],
  ])('%s', (_label, input, expected) => {
    expect(fn(input)).toBe(expected);
  });

  it('single edge-case description', () => {
    expect(fn(edgeCaseInput)).toBe(edgeCaseExpected);
  });
});
```

#### Section rules

| Section | Rule |
|---|---|
| `// Libs imports` | Third-party packages only (`vitest`, `dayjs`, etc.) |
| `// Mocks` | All `vi.mock()` calls. Always placed **before** `// App imports`. Vitest hoists these automatically. Mock state objects referenced in factory closures may be defined here too. |
| `// App imports` | Project modules (`@/modules/...`, `@/components/...`) |
| `// Fixtures` | Shared constants and factory helpers used across test suites in the file |

#### Parametrization — Default to `it.each`

**Always prefer `it.each` over multiple `it` blocks that repeat the same assertion logic.**
This is the Vitest equivalent of pytest's `@pytest.mark.parametrize`.

```js
// ✅ Preferred
it.each([
  ['past date', -2, true],
  ['future date', 2, false],
])('%s → disableThePast returns %s', (_label, offset, expected) => {
  expect(disableThePast(dayjs().add(offset, 'day'))).toBe(expected);
});

// ❌ Avoid
it('returns true for a past date', () => { ... });
it('returns false for a future date', () => { ... });
```

Rules:
- Use `it.each` whenever **2 or more** test cases share the same assertion structure.
- Unused parameters in `it.each` callbacks must be prefixed with `_` (e.g., `_label`).
- Name the test using `%s` / `%i` / `%o` placeholders from the table row to produce self-documenting output.
- Use factory functions (e.g., `makeChatMessage()`) for complex fixture objects so each `it.each` row stays concise.

#### `vi.mock` Placement

`vi.mock` calls are **statically hoisted** by Vitest to run before any ES module imports, regardless of where they appear in the file. To make this explicit:

- Always place `vi.mock` calls in a dedicated `// Mocks` section **between** `// Libs imports` and `// App imports`.
- Mock state objects referenced inside factory closures **must** be declared with `vi.hoisted()` so they are available when the factory runs (regular `const` declarations are in TDZ at that point):
  ```js
  // Mocks
  const { mockSocket } = vi.hoisted(() => ({
    mockSocket: { close: vi.fn(), send: vi.fn() },
  }));

  vi.mock('@/modules/websocket/chat', () => ({ default: vi.fn(() => mockSocket) }));
  ```
- Always call `vi.clearAllMocks()` inside `beforeEach` when mocks are present.
- When testing code that uses `async` timers (e.g., WebSocket reconnect logic), use `await vi.advanceTimersByTimeAsync(ms)` instead of the synchronous `vi.advanceTimersByTime(ms)` to flush pending microtasks.

#### Naming Conventions
- Test files: `*.test.js` for unit/component tests, `*.spec.js` for E2E.
- `describe` labels: `ClassName.methodName` (e.g., `Auth.getUserType`).
- `it` / `it.each` labels: plain English, outcome-focused (e.g., `'renders the sign-in form when unauthenticated'`).

---

## 5. Environment Variables & Authentication

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
