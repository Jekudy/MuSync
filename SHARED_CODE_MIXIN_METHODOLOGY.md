# Shared Code & Mixin Methodology Guide

## Overview

This guide outlines a stack-agnostic methodology for using shared code and mixins to reduce duplication, improve maintainability, and speed up development.

## Core Principles

### 1. Mixin-First Approach
- Identify common functionality before implementing specific features
- Create mixins (or traits/components) for shared behavior
- Compose features using mixins rather than deep inheritance
- Test mixins in isolation and in combination

### 2. Shared Code Patterns
- Extract common UI/interaction patterns into reusable components
- Centralize validation and error handling
- Implement common data access operations
- Build shared workflow/state patterns

### 3. Composition Over Inheritance
- Keep inheritance hierarchies shallow
- Prefer composition for complex relationships
- Make components easily testable

## Example Categories (Generic)

## Recommended Mixin Categories

### 1. Navigation & Pagination (pseudo)

```pseudo
trait NavigationMixin {
  async handleBack(req, ctx): void
  async showMainView(req, ctx): void
}
```

```pseudo
trait PaginationMixin {
  async handlePageChange(req, ctx, page: int): void
}
```

### 2. Validation & Authorization (pseudo)

```pseudo
trait ServiceValidationMixin {
  async ensureExists(repo, id): Entity
  async requirePermission(subject, resource, permission): void
}
```

```pseudo
trait TimeValidationMixin {
  validateTimeRange(start, end): void
}
```

### 3. Repository Helpers (pseudo)

```pseudo
trait RepositoryCrudMixin<T> {
  async create(entity: T): Id
  async getById(id: Id): Optional<T>
  async update(entity: T): void
  async delete(id: Id): bool
}
```

```pseudo
trait RepositoryQueryMixin<T> {
  async listByOwner(ownerId: Id): List<T>
  async listActive(): List<T>
}
```

### 4. Workflow State Management (pseudo)

```pseudo
trait WorkflowStateMixin {
  setState(userId: Id, state: string, data: Map): void
  getState(userId: Id): Optional<Map>
  clearState(userId: Id): void
  isInState(userId: Id, state: string): bool
}
```

### 5. Notification/Feedback (pseudo)

```pseudo
trait NotificationMixin {
  async notify(userId: Id, message: string, options?): void
}
```

## Implementation Guidelines

### When to Create Mixins

Create mixins when you identify:
- Common UI/interaction patterns (menus, navigation, pagination)
- Shared business logic (validation, authorization, error handling)
- Repeated data access operations (CRUD, queries)
- Similar workflow/state steps

### Mixin Design Principles

- Single responsibility with a clear interface
- Descriptive method names and type hints where applicable
- Minimal assumptions about the host class
- Easy to test in isolation

### Naming Conventions

- End names with "Mixin" (or language-idiomatic alternative)
- Group related functionality together
- Use intent-revealing method names

### Testing Mixins (pseudo)

```pseudo
test "navigation mixin back button" {
  host = WorkflowWith(NavigationMixin)
  expect(await host.handleBack(req, ctx)).toSucceed()
}
```

## Usage Examples (Generic)

### 1. Workflow with Multiple Mixins (pseudo)

```pseudo
class AdminWorkflow extends BaseWorkflow with NavigationMixin, NotificationMixin {
  async handle(req, ctx) {
    if (req.action == "back") return await this.handleBack(req, ctx)
    if (req.action == "notify") return await this.notify(req.userId, req.message)
  }
}
```

### 2. Service with Validation Mixins (pseudo)

```pseudo
class ResourceService with ServiceValidationMixin {
  constructor(repo) { this.repo = repo }
  async activate(id: Id) {
    resource = await this.ensureExists(this.repo, id)
    resource.isActive = true
    await this.repo.update(resource)
    return resource
  }
}
```

### 3. Repository with CRUD Mixins (pseudo)

```pseudo
class ResourceRepository with RepositoryCrudMixin<Resource>, RepositoryQueryMixin<Resource> {}
```

## Migration Strategy

### 1. Identify Existing Patterns
- Analyze current workflows for common functionality
- Look for repeated code patterns
- Identify similar UI components
- Find shared validation logic

### 2. Create Mixins Incrementally
- Start with the most common patterns
- Create one mixin at a time
- Test thoroughly before using in production
- Document usage patterns

### 3. Refactor Existing Code
- Gradually replace repeated code with mixins
- Maintain backward compatibility
- Update tests to use mixins
- Document changes

### 4. Measure Success
- Track code duplication reduction
- Measure development speed improvements
- Monitor bug reduction
- Assess maintainability improvements

## Success Metrics

### Code Quality
- Reduced duplication: >30% in target areas
- Improved testability: shared functionality easier to test
- Better maintainability: changes in one place affect all usages
- Consistent behavior across similar features

### Development Speed
- Faster feature development via reuse
- Reduced debugging: shared code is tested once
- Easier onboarding: clear patterns to follow
- Consistent architecture across modules

## Best Practices

### 1. Start Small
- Begin with simple, well-understood patterns
- Create mixins for the most common functionality
- Gradually expand to more complex patterns

### 2. Test Thoroughly
- Test mixins in isolation and in combination
- Cover edge cases and error conditions
- Verify backward compatibility when refactoring

### 3. Document Everything
- Document mixin purpose and usage
- Provide clear examples
- Explain when to use each mixin
- Keep documentation up to date

### 4. Review Regularly
- Periodically review mixin usage
- Identify new shared patterns
- Refactor as needed
- Remove obsolete mixins

This methodology ensures shared code delivers tangible productivity without sacrificing clarity, testability, or maintainability.