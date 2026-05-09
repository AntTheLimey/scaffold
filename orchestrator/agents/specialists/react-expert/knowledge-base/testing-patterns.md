# React Testing Patterns

## React Testing Library

Test user behavior, not implementation details.

### Basic rendering and queries

```tsx
import { render, screen } from "@testing-library/react";
import { UserCard } from "./UserCard";

test("displays user name and email", () => {
  render(<UserCard name="Alice" email="alice@example.com" />);

  expect(screen.getByText("Alice")).toBeInTheDocument();
  expect(screen.getByText("alice@example.com")).toBeInTheDocument();
});
```

### Query priority (most to least preferred)

1. `getByRole` — accessible role (button, heading, textbox)
2. `getByLabelText` — form elements by their label
3. `getByPlaceholderText` — inputs by placeholder
4. `getByText` — visible text content
5. `getByDisplayValue` — form elements by current value
6. `getByTestId` — last resort, `data-testid` attribute

Prefer accessible queries. If you cannot query by role or label, the
component may have accessibility issues.

## userEvent

Use `@testing-library/user-event` for user interactions:

```tsx
import userEvent from "@testing-library/user-event";

test("calls onSubmit when form is submitted", async () => {
  const user = userEvent.setup();
  const onSubmit = vi.fn();

  render(<LoginForm onSubmit={onSubmit} />);

  await user.type(screen.getByLabelText("Email"), "alice@example.com");
  await user.type(screen.getByLabelText("Password"), "secret123");
  await user.click(screen.getByRole("button", { name: "Log in" }));

  expect(onSubmit).toHaveBeenCalledWith({
    email: "alice@example.com",
    password: "secret123",
  });
});
```

### userEvent vs fireEvent

- `userEvent` simulates real user interactions (typing fires keydown,
  keypress, input, keyup). Preferred.
- `fireEvent` dispatches a single DOM event. Use only when userEvent
  does not support the interaction.

## act() and Async

### Async state updates

```tsx
test("loads data on mount", async () => {
  render(<UserList />);

  // waitFor retries until the assertion passes or times out
  await waitFor(() => {
    expect(screen.getByText("Alice")).toBeInTheDocument();
  });
});

test("shows loading then content", async () => {
  render(<UserList />);

  expect(screen.getByText("Loading...")).toBeInTheDocument();

  // findBy is shorthand for waitFor + getBy
  expect(await screen.findByText("Alice")).toBeInTheDocument();
  expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
});
```

### When act() is needed

`act()` is usually called automatically by Testing Library. You need it
manually only when:

- Triggering state updates outside of Testing Library helpers.
- Using timers (`jest.advanceTimersByTime` inside act).

## Mocking Modules

### Mock API calls

```tsx
import { vi } from "vitest";
import * as api from "./api";

vi.mock("./api");
const mockFetchUsers = vi.mocked(api.fetchUsers);

test("renders fetched users", async () => {
  mockFetchUsers.mockResolvedValue([
    { id: "1", name: "Alice" },
    { id: "2", name: "Bob" },
  ]);

  render(<UserList />);

  expect(await screen.findByText("Alice")).toBeInTheDocument();
  expect(screen.getByText("Bob")).toBeInTheDocument();
});
```

### Mock router

```tsx
import { MemoryRouter } from "react-router-dom";

function renderWithRouter(ui: React.ReactElement, { route = "/" } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      {ui}
    </MemoryRouter>
  );
}

test("navigates to settings page", async () => {
  const user = userEvent.setup();
  renderWithRouter(<App />, { route: "/" });

  await user.click(screen.getByRole("link", { name: "Settings" }));
  expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
});
```

## Testing Custom Hooks

```tsx
import { renderHook, act } from "@testing-library/react";
import { useCounter } from "./useCounter";

test("increments counter", () => {
  const { result } = renderHook(() => useCounter(0));

  expect(result.current.count).toBe(0);

  act(() => {
    result.current.increment();
  });

  expect(result.current.count).toBe(1);
});
```

Prefer testing hooks through a component when possible. Use `renderHook`
only for hooks that are genuinely reusable and tested in isolation.

## Anti-Patterns

- **Snapshot tests for components**: Snapshots test structure, not behavior.
  They break on any render change and teach developers to blindly update.
- **Testing state directly**: Never assert `useState` values. Assert what
  the user sees on screen.
- **Querying by class name or tag**: Couples tests to styling. Use roles
  and labels instead.
- **Not awaiting async operations**: Missing `await` causes act warnings
  and unreliable tests.
- **Testing internal component state**: Use `screen.getByText` to check
  what is rendered, not component internals.
