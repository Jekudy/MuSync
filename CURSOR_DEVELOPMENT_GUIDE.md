# 🚀 Cursor Development Guide: From Beginner to Pro

## 📋 Table of Contents

1. [Philosophy & Approach](#philosophy--approach)
2. [Cursor Setup](#cursor-setup)
3. [Development Methodology](#development-methodology)
4. [Prompting Strategies](#prompting-strategies)
5. [Project Structure](#project-structure)
6. [Testing Strategy](#testing-strategy)
7. [Step-by-Step Workflow](#step-by-step-workflow)

---

## 🎯 Philosophy & Approach

### Core Principles

1. Test-Driven Development (write tests first)
2. Prefer async/parallel designs where it improves UX/perf
3. Document decisions and public interfaces
4. Incremental development with working tests
5. Production-readiness: reliability, observability, security

### Development Mindset

- Think in user scenarios and acceptance criteria
- Fail fast via tests and feature flags
- Keep a living architecture (ADRs)
- Iterate in small, safe steps

---

## ⚙️ Cursor Setup

### Step 1: Install Cursor

Download from `https://cursor.sh` and install

### Step 2: Configure Your Environment

Create a `.cursorrules` file with stack-agnostic rules. Example:

```markdown
# Project Rules

## Code Standards
- Use type hints and a formatter/linter
- Prefer async where helpful
- Write tests for new features

## Architecture
- Repositories for data access
- Services/use-cases for business logic
- Mixins/components for shared behavior

## Workflow
1) Feature description → 2) Tests → 3) Implementation → 4) Integration tests → 5) Docs
```

### Step 3: Editor/Tooling Extensions (example)

```json
{
  "extensions": [
    "editorconfig.editorconfig",
    "streetsidesoftware.code-spell-checker"
  ]
}
```

---

## 🏗️ Development Methodology

### 1. Feature-Driven Development with Shared Code

```
Feature request → Identify shared code → Create/extend mixins → Scenario → Tests → Implementation → Integration tests → Docs
```

### 2. Mixin-First Approach

- Identify common patterns before coding specifics
- Extract shared behavior into reusable mixins/components
- Test mixins in isolation and in composition

### 3. Test-First Approach (pseudo)

```pseudo
test "user can register" {
  service = createUserService(fakeRepo)
  user = service.register("john")
  expect(user.name == "john")
}
```

### 4. Async-First Sketch (pseudo)

```pseudo
async registerUser(name) -> User {
  ensure(!(await repo.exists(name)))
  id = await repo.create(User(name))
  return User(id, name)
}
```

---

## 💬 Prompting Strategies

### 1. Context-Rich Prompts

```
I'm building a new product with a repository/service architecture.
I need to implement: [feature]

Relevant structure:
[describe modules]

Please help me:
1) Write a scenario test
2) Implement the feature
3) Add integration tests
4) Update docs
```

### 2. Scenario-Based Prompts

```
Implement a confirmation workflow where:
1) User submits a request
2) Approver is notified
3) Approver confirms or rejects
4) Requester sees the decision

Please guide step by step, starting with tests.
```

### 3. Debugging Prompts

```
I'm getting this error:
[error]

Test code:
[snippet]

Service code:
[snippet]

Please help identify and fix the issue.
```

---

## 📁 Project Structure (Generic)

```
project/
├── app/
│   ├── domain/            # Entities, value objects, rules
│   ├── application/       # Use cases/services
│   ├── infrastructure/    # Repos, integrations
│   └── interfaces/        # API/UI/Bot/CLI
├── tests/                 # Unit/integration/e2e
├── docs/                  # Docs and ADRs
└── config/                # Env/config
```

---

## 🧪 Testing Strategy

### 1. Test Categories (pseudo)

```pseudo
test unit "service registers user" { ... }
test integration "workflow succeeds with db" { ... }
test e2e "user completes scenario" { ... }
```

### 2. Test Configuration

- Use an async-capable test runner where relevant
- Provide fakes/mocks for external dependencies
- Run tests in CI with clear reports

---

## 🔄 Step-by-Step Workflow

### Phase 1: Plan with Shared Code Analysis

1. Write a one-page feature description (problem, scope, acceptance criteria)
2. Identify shared patterns (navigation, CRUD, validation, state)
3. Design/extend mixins/components
4. Draft scenario tests

### Phase 2: Core Implementation

1. Implement domain entities and validations
2. Implement use cases/services using repositories
3. Add observability and error handling

### Phase 3: Integration & E2E

1. Write integration tests with real adapters where safe
2. Add end-to-end tests for critical paths
3. Update docs and examples

---

## 🎯 Common Patterns & Best Practices

### 1. Mixin Pattern (pseudo)

```pseudo
trait NavigationMixin { async handleBack(req, ctx) }
```

### 2. Repository Pattern (pseudo)

```pseudo
port Repository<T> { create(T): Id; getById(Id): T? }
```

### 3. Error Handling (pseudo)

```pseudo
error DomainError; error ValidationError extends DomainError
```

### 4. Workflow Composition

- Compose small, testable steps
- Keep side effects at boundaries

---

## 🚀 Getting Started Checklist

### Day 1: Setup

- [ ] Install Cursor
- [ ] Create `.cursorrules`
- [ ] Configure formatter/linter and tests
- [ ] Run initial CI

### Day 2: First Feature with Shared Code

- [ ] Feature description
- [ ] Identify shared code
- [ ] Write scenario test
- [ ] Implement with mixins/components
- [ ] Integration tests
- [ ] Update docs

### Day 3: Advanced Patterns

- [ ] Repository CRUD mixins
- [ ] Validation/authorization mixins
- [ ] Observability and error taxonomy
- [ ] E2E tests for critical flows
- [ ] Architecture ADRs

---

## 📚 Resources & References

- Team style guide and ADRs in `docs/`
- Testing framework and runner docs (stack-specific)
- Observability and security best practices

### Success Metrics

- [ ] All tests passing in CI
- [ ] No lint/type errors
- [ ] Docs up to date
- [ ] Error handling and logging in place

Remember: pair solid prompting with disciplined engineering. Write tests first, prefer async where helpful, identify shared code early, compose with mixins, and document as you go.
