# Component Boundaries Reference

## Single Responsibility Principle

A component (module, service, class, file) should have exactly one reason to
change. "Reason to change" means one stakeholder or one category of requirements.

Testing for single responsibility:
- Describe the component in one sentence without "and." If you need "and," it
  has two responsibilities.
- List who would request changes to this component. If the answer includes
  multiple distinct roles (e.g., "the DBA and the UI designer"), it has
  multiple responsibilities.
- Count the reasons this component might change. If more than one independent
  change driver exists, split.

Example of violation: A UserService that handles registration (business logic),
password hashing (security), and email sending (infrastructure). These change
for different reasons and at different rates.

Fix: UserService (registration logic), PasswordHasher (security), EmailSender
(infrastructure).

## Dependency Direction

Dependencies should flow in one direction: from higher-level policy to
lower-level detail. Concretely:

```
Routes → Services → Repositories → Database
  ↓
Views → Components → Hooks
```

Rules:
- A module may depend on modules at the same level or below. Never above.
- Infrastructure (database, HTTP, file system) is the lowest level.
- Business logic sits above infrastructure and never imports from it directly.
  It depends on abstractions (interfaces/protocols) that infrastructure implements.
- Presentation (routes, views) sits above business logic.

Detecting violations:
- If changing a database driver requires modifying business logic, the dependency
  direction is wrong.
- If a utility module imports from a feature module, the dependency is inverted.
- Circular imports are always a boundary violation.

## Splitting Signals

A component should be split when:

- **File length exceeds ~300 lines**: Not a hard rule, but a signal. Long files
  usually contain multiple responsibilities.
- **Import list grows beyond 10 items**: Many imports suggest the module is
  coordinating too many concerns.
- **Test file is significantly longer than source**: If testing one module
  requires elaborate setup for unrelated behaviors, the module does too much.
- **Changes to one feature frequently touch this module**: Shared code that
  changes often should be split so that each feature owns its own piece.
- **Naming becomes awkward**: If functions in a module need prefixes to
  disambiguate (user_validate, order_validate), they belong in separate modules.

A component should NOT be split when:
- The "split" would create two modules that always change together.
- The split introduces a new abstraction layer that adds complexity but no value.
- The component is small (<50 lines) and cohesive.

## Cohesion Metrics

High cohesion means every part of a component is related to its single purpose.
Low cohesion means the component is a grab-bag of loosely related functions.

Signs of low cohesion:
- Functions in the module that do not call each other or share data.
- Half the module's functions are used by one consumer, the other half by another.
- The module name is generic: "utils," "helpers," "common," "misc."

Fix: Group functions by their consumer or their data affinity. Move them into
focused modules named after what they do, not where they live.

## Boundary Communication

Components communicate across boundaries via:

- **Function calls**: Direct invocation. Tight coupling but simple. Use within
  a single process for same-responsibility interactions.
- **Interfaces/Protocols**: Define the contract, let the implementation vary.
  Use when a component should be replaceable (repositories, external services).
- **Events**: One component emits, others subscribe. Use when the producer should
  not know about consumers (logging, analytics, notifications).
- **Message queues**: Asynchronous, persistent. Use when operations can tolerate
  delay and need durability (email sending, report generation).

Choose the simplest mechanism that meets the requirements. Do not introduce
events or queues unless synchronous calls create unacceptable coupling or
latency.

## Package/Module Organization

Organize by feature, not by layer:

```
Prefer:                      Avoid:
features/                    controllers/
  auth/                        user_controller
    routes                     order_controller
    service                  services/
    repository                 user_service
  orders/                      order_service
    routes                   repositories/
    service                    user_repository
    repository                 order_repository
```

Feature-based organization keeps related code together. Layer-based organization
scatters a feature across many directories, making it hard to understand or
modify as a unit.

Exception: truly shared infrastructure (database connection, HTTP client config,
logging setup) belongs in a shared/infra directory.
