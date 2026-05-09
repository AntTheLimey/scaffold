# TypeScript Testing Patterns

## vitest / jest Patterns

### Test file structure

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { parseConfig } from "./config";

describe("parseConfig", () => {
  it("parses valid YAML into Config object", () => {
    const input = "port: 8080\nhost: localhost";
    const result = parseConfig(input);

    expect(result).toEqual({
      port: 8080,
      host: "localhost",
    });
  });

  it("throws ParseError for malformed input", () => {
    expect(() => parseConfig(": invalid :")).toThrow(ParseError);
  });

  it("returns default values for missing optional fields", () => {
    const result = parseConfig("port: 8080");
    expect(result.host).toBe("0.0.0.0");
  });
});
```

### Naming conventions

- Files: `*.test.ts` or `*.spec.ts` — match the project's convention.
- Describe blocks: match the function or class name.
- It blocks: describe the behavior in plain English.

### Setup and teardown

```typescript
describe("UserService", () => {
  let service: UserService;
  let mockRepo: MockRepository;

  beforeEach(() => {
    mockRepo = createMockRepository();
    service = new UserService(mockRepo);
  });

  it("creates a user with hashed password", async () => {
    await service.create({ email: "a@b.com", password: "secret" });
    expect(mockRepo.save).toHaveBeenCalledWith(
      expect.objectContaining({
        email: "a@b.com",
        passwordHash: expect.any(String),
      })
    );
  });
});
```

## vi.mock (vitest) / jest.mock

### Module mocking

```typescript
import { vi } from "vitest";
import { fetchData } from "./api";
import { processData } from "./processor";

vi.mock("./api");
const mockFetchData = vi.mocked(fetchData);

describe("processData", () => {
  it("transforms fetched data", async () => {
    mockFetchData.mockResolvedValue({ items: [1, 2, 3] });

    const result = await processData();

    expect(result).toEqual([2, 4, 6]);
    expect(mockFetchData).toHaveBeenCalledOnce();
  });

  it("throws on fetch failure", async () => {
    mockFetchData.mockRejectedValue(new Error("network error"));

    await expect(processData()).rejects.toThrow("network error");
  });
});
```

### Partial mocking

```typescript
vi.mock("./utils", async () => {
  const actual = await vi.importActual<typeof import("./utils")>("./utils");
  return {
    ...actual,
    fetchConfig: vi.fn().mockReturnValue({ debug: true }),
  };
});
```

### Timer mocking

```typescript
describe("debounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("calls function after delay", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 300);

    debounced();
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(300);
    expect(fn).toHaveBeenCalledOnce();
  });
});
```

## Type-Level Tests

Verify that types work correctly at compile time:

```typescript
import { expectTypeOf } from "vitest";

it("infers correct return type", () => {
  const result = parseConfig("port: 8080");
  expectTypeOf(result).toEqualTypeOf<Config>();
});

it("rejects invalid input types", () => {
  // @ts-expect-error — number is not valid input
  parseConfig(42);
});

it("preserves generic type parameter", () => {
  const repo = new Repository<User>();
  expectTypeOf(repo.getAll()).toEqualTypeOf<User[]>();
});
```

### @ts-expect-error as a test

Use `@ts-expect-error` to verify that invalid code produces a type error.
If the code compiles without error, TypeScript will report an unused
`@ts-expect-error` directive — making the test fail.

```typescript
// Verify that mismatched types are caught
// @ts-expect-error — string is not assignable to number
const count: number = "five";
```

## Async Testing

```typescript
describe("async operations", () => {
  it("resolves with data", async () => {
    const result = await fetchUser("123");
    expect(result.name).toBe("Alice");
  });

  it("rejects with typed error", async () => {
    await expect(fetchUser("unknown")).rejects.toThrow(NotFoundError);
  });

  it("handles concurrent operations", async () => {
    const results = await Promise.all([
      fetchUser("1"),
      fetchUser("2"),
      fetchUser("3"),
    ]);
    expect(results).toHaveLength(3);
  });
});
```

## Anti-Patterns

- **Casting in tests**: If you need `as any` to make a test work, the
  test setup is wrong. Fix the root cause.
- **Testing types at runtime when compile-time suffices**: Use
  `expectTypeOf` for type assertions, not runtime `typeof` checks.
- **Mocking everything**: Mock external boundaries only (HTTP, database,
  file system). Test internal logic with real objects.
- **Not testing error paths**: Every function that can throw or reject
  needs a test that verifies the error type and message.
- **Snapshot tests for data structures**: Use explicit assertions instead.
- **Ignoring async warnings**: Always `await` async operations in tests.
