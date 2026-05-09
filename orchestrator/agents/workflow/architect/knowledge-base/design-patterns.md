# Design Patterns Reference

## Repository Pattern

**What**: Abstracts data persistence behind a collection-like interface. The
business logic works with domain objects; the repository handles storage.

**Interface**:
```
Repository<T>:
  find(id) -> T | None
  find_all(filter) -> list[T]
  save(entity: T) -> T
  delete(id) -> void
```

**When to use**: When business logic should not know how data is stored. When
you want to swap storage mechanisms (database, file, in-memory for tests).

**When NOT to use**: For simple CRUD apps where the business logic IS the
database operations. Adding a repository layer that just passes through calls
adds indirection without value.

**YAGNI signal**: If your repository methods mirror your ORM methods 1:1 with
no additional logic, you probably do not need the pattern yet.

## Strategy Pattern

**What**: Encapsulates a family of algorithms behind a common interface, allowing
the algorithm to be selected at runtime.

**Structure**:
```
Strategy interface:
  execute(input) -> output

ConcreteStrategyA implements Strategy
ConcreteStrategyB implements Strategy

Context:
  strategy: Strategy
  run(input) -> strategy.execute(input)
```

**When to use**: When you have multiple ways to perform the same operation and
the choice depends on runtime conditions. Examples: different pricing rules per
customer tier, different file parsers per format, different notification channels.

**When NOT to use**: When there are only two options and no expectation of more.
A simple if/else is clearer than a strategy hierarchy for two cases.

**YAGNI signal**: If you create a strategy interface with only one implementation
and "might add more later," you are speculating. Start with the concrete
implementation and extract the pattern when the second case arrives.

## Factory Pattern

**What**: Encapsulates object creation, hiding the complexity of choosing and
configuring the right concrete type.

**Variants**:
- **Factory method**: A single function that returns the right type based on
  input. `create_parser(file_type) -> Parser`
- **Abstract factory**: An interface for creating families of related objects.
  `UIFactory.create_button()`, `UIFactory.create_dialog()`

**When to use**: When object creation involves logic (choosing between subtypes,
applying configuration, validating prerequisites) that should not be scattered
across the codebase.

**When NOT to use**: When construction is straightforward. `User(name, email)` does
not need a factory. Factories add a layer of indirection; that cost must be
justified by the complexity of creation logic.

**YAGNI signal**: A factory that always returns the same type. If there is no
variation in what gets created, the factory adds no value.

## Observer Pattern

**What**: Defines a one-to-many relationship where one object (subject) notifies
multiple dependents (observers) of state changes.

**Structure**:
```
Subject:
  observers: list[Observer]
  attach(observer)
  detach(observer)
  notify() -> calls update() on all observers

Observer:
  update(event) -> void
```

**When to use**: When a change in one component should trigger actions in others,
but the triggering component should not know about or depend on the receivers.
Examples: audit logging, cache invalidation, UI updates from model changes.

**When NOT to use**: When the observer chain creates hidden control flow that
makes the system hard to debug. If tracing "what happens when X changes"
requires reading 5 different observer registrations, the pattern is hurting.

**YAGNI signal**: If you have exactly one observer, you do not need the pattern.
Call the function directly and extract the observer pattern when a second
consumer appears.

## General YAGNI Guidance

Apply patterns when:
1. You have concrete evidence of the variation point (two or more implementations).
2. The pattern simplifies the code (fewer total lines, clearer intent).
3. The pattern enables testability that is otherwise difficult.

Do NOT apply patterns when:
1. You are guessing about future requirements.
2. The pattern adds more code than the direct approach.
3. The only justification is "best practice" or "might need it later."

The cost of extracting a pattern later, when the need is proven, is almost
always lower than the cost of maintaining a premature abstraction. Design for
today's requirements with an eye toward tomorrow's, but only build today's.

## Pattern Combinations

Common effective combinations:
- **Repository + Factory**: Factory creates the right repository implementation
  based on configuration (SQL vs in-memory for tests).
- **Strategy + Factory**: Factory selects the strategy based on runtime context.
- **Observer + Strategy**: Different observers apply different strategies for
  handling the same event type.

Dangerous combinations:
- **Factory + Factory**: Factories creating factories. If you are building
  factory hierarchies, reconsider the design.
- **Observer chains**: Observer A notifies Observer B which notifies Observer C.
  Event cascades are hard to debug and reason about.
