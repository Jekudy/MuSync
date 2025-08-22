# MVP Architecture Template

This document defines a stack-agnostic architecture template for a new product. It focuses on clear boundaries, testability, and reuse.

## Project Structure (Generic)

```
app/
├── domain/                # Core business concepts (entities, value objects, rules)
├── application/           # Use cases/services orchestrating domain logic
├── infrastructure/        # DB, messaging, external integrations, implementations
├── interfaces/            # Delivery layer: HTTP/API, UI, Bot, CLI, etc.
├── crosscutting/          # Logging, tracing, config, auth, DI containers
├── tests/                 # Unit, integration, end-to-end tests
├── docs/                  # Documentation and ADRs
└── config/                # Environment and deployment configs
```

## Architecture Layers

### 1. Domain Layer (Pure)
- Business entities and invariants
- No framework or I/O dependencies
- Validation and rules live here

### 2. Application Layer (Use Cases)
- Coordinates operations across repositories and external services
- Encodes business workflows and policies
- Depends only on domain abstractions and ports

### 3. Infrastructure Layer (Adapters)
- Concrete implementations of repositories, message brokers, storage, external APIs
- Handles transactions, retries, and mapping to domain models

### 4. Interfaces Layer (Delivery)
- API controllers, UI/Bot handlers, CLI commands, scheduled jobs
- Translates requests to use cases and results to responses

### 5. Cross-Cutting Concerns
- Logging, metrics, tracing
- Configuration and secrets management
- Authentication and authorization
- Dependency injection

## Data Flow (Typical)

```
Client → Interface (controller/handler) → Application (use case) → Domain (entities/rules)
       ←            Infrastructure (repo/adapters) ←
```

## Key Principles

- Separation of concerns and clear boundaries
- Dependency inversion: outer layers depend on inner abstractions
- Testability first: each layer can be tested in isolation
- Framework independence in domain/application
- Explicit error handling and observability

## Module Responsibilities (Sketches)

### Domain Entities
```pseudo
entity Resource {
  id: Id
  name: string
  isActive: bool
}
```

### Application Use Case
```pseudo
usecase ActivateResource(resourceId: Id) -> Result {
  resource = resourceRepository.getById(resourceId)
  ensure(resource != null)
  resource.isActive = true
  resourceRepository.update(resource)
  return Ok(resource)
}
```

### Repository Port
```pseudo
port ResourceRepository {
  getById(id: Id): Optional<Resource>
  create(r: Resource): Id
  update(r: Resource): void
}
```

### Interface Controller
```pseudo
controller POST /resources/{id}/activate {
  result = ActivateResource(id)
  return toHttpResponse(result)
}
```

## Configuration & Environments

- Dependencies wired via DI container per environment
- Use environment variables and config files
- Separate configs for dev/staging/prod; secure secrets

## Observability

- Structured logging with correlation IDs
- Metrics on key flows and errors
- Tracing across interfaces, application, and infrastructure

This template enables fast iteration with a maintainable, testable structure that is independent of specific frameworks or databases.