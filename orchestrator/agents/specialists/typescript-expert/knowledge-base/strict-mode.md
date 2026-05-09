# TypeScript Strict Mode

## Strict Compiler Options

### Core strict flags

When `"strict": true` is set in tsconfig.json, it enables all of these:

- `strictNullChecks`: `null` and `undefined` are distinct types. Variables are
  not nullable unless explicitly typed as `T | null`.
- `strictFunctionTypes`: Function parameter types are checked contravariantly.
- `strictBindCallApply`: `bind`, `call`, and `apply` are type-checked.
- `strictPropertyInitialization`: Class properties must be initialized in the
  constructor or marked with `!`.
- `noImplicitAny`: Every value must have a known type. No implicit `any`.
- `noImplicitThis`: `this` must have an explicit type in functions.
- `useUnknownInCatchVariables`: Catch variables are `unknown`, not `any`.
- `alwaysStrict`: Emits `"use strict"` in all files.

### Additional strictness flags

Enable these beyond `strict: true` for maximum safety:

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noPropertyAccessFromIndexSignature": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noImplicitOverride": true
  }
}
```

- `noUncheckedIndexedAccess`: Array/object index access returns `T | undefined`.
- `exactOptionalPropertyTypes`: Optional properties cannot be set to `undefined`
  explicitly unless the type includes `undefined`.
- `noPropertyAccessFromIndexSignature`: Forces bracket notation for index
  signatures, distinguishing known from dynamic properties.

## Type Narrowing

### typeof guards

```typescript
function format(value: string | number): string {
  if (typeof value === "string") {
    return value.toUpperCase(); // narrowed to string
  }
  return value.toFixed(2); // narrowed to number
}
```

### instanceof guards

```typescript
function getLength(value: string | string[]): number {
  if (Array.isArray(value)) {
    return value.length; // narrowed to string[]
  }
  return value.length; // narrowed to string
}
```

### Discriminated unions

```typescript
type Result<T> =
  | { ok: true; value: T }
  | { ok: false; error: Error };

function handle<T>(result: Result<T>): T {
  if (result.ok) {
    return result.value; // narrowed to { ok: true; value: T }
  }
  throw result.error; // narrowed to { ok: false; error: Error }
}
```

### in operator

```typescript
interface Dog { bark(): void; }
interface Cat { meow(): void; }

function speak(animal: Dog | Cat) {
  if ("bark" in animal) {
    animal.bark(); // narrowed to Dog
  } else {
    animal.meow(); // narrowed to Cat
  }
}
```

## Assertion Functions

Functions that assert a condition or throw:

```typescript
function assertDefined<T>(
  value: T | null | undefined,
  message: string
): asserts value is T {
  if (value === null || value === undefined) {
    throw new Error(message);
  }
}

// Usage
const user = getUser(id);  // User | null
assertDefined(user, `User ${id} not found`);
user.name; // narrowed to User — no null check needed
```

### Type predicate functions

```typescript
function isString(value: unknown): value is string {
  return typeof value === "string";
}

function process(values: unknown[]): string[] {
  return values.filter(isString); // returns string[], not unknown[]
}
```

## Branded Types

Prevent type confusion between structurally identical types:

```typescript
type UserId = string & { readonly __brand: "UserId" };
type OrderId = string & { readonly __brand: "OrderId" };

function createUserId(id: string): UserId {
  return id as UserId;
}

function getUser(id: UserId): User { ... }

const userId = createUserId("u-123");
const orderId = "o-456" as OrderId;

getUser(userId);  // OK
getUser(orderId); // Type error: OrderId is not assignable to UserId
getUser("raw");   // Type error: string is not assignable to UserId
```

Use branded types for:
- IDs that should not be interchanged (UserId, OrderId, SessionId).
- Validated strings (Email, PhoneNumber, URL).
- Units that should not be mixed (Meters, Kilometers, Pixels).

## satisfies Operator

Type-check an expression without widening its type:

```typescript
const config = {
  port: 8080,
  host: "localhost",
  debug: true,
} satisfies Record<string, string | number | boolean>;

// config.port is number (not string | number | boolean)
// config.unknown would be a type error at definition
```

Use `satisfies` instead of type annotation when you want:
- Type checking at the definition site.
- Inference to preserve the narrow type (literal types, specific keys).

## Common Patterns

### Exhaustive switch

Use `assertNever(value: never): never` in the default case of a switch
on a discriminated union. If a case is missing, TypeScript reports a
compile error because the value is not `never`.

### DeepReadonly

```typescript
type DeepReadonly<T> = {
  readonly [K in keyof T]: T[K] extends object ? DeepReadonly<T[K]> : T[K];
};
```

Use for configuration objects that should not be mutated after loading.
