# React Accessibility

## Semantic HTML

Use the correct HTML element for its purpose. Semantic elements provide
built-in accessibility for free.

### Element selection

| Purpose             | Use                    | Not                            |
| ------------------- | ---------------------- | ------------------------------ |
| Navigation          | `<nav>`                | `<div className="nav">`        |
| Page section        | `<section>`, `<main>`  | `<div className="section">`    |
| Heading hierarchy   | `<h1>` through `<h6>`  | `<div className="title">`      |
| Button action       | `<button>`             | `<div onClick={...}>`          |
| Link to another URL | `<a href="...">`       | `<button onClick={navigate}>`  |
| List of items       | `<ul>`, `<ol>`, `<li>` | Nested `<div>` elements        |
| Form input          | `<input>`, `<select>`  | Content-editable div           |
| Table data          | `<table>`, `<th>`      | CSS grid of divs               |

### Heading hierarchy

- Every page has exactly one `<h1>`.
- Headings do not skip levels (h1 then h3 without h2).
- Headings describe the content that follows.

## ARIA Roles and Attributes

Use ARIA only when semantic HTML is insufficient. The first rule of ARIA:
do not use ARIA if a native HTML element provides the semantics.

### Common patterns

```tsx
// Alert for dynamic status messages
<div role="alert">Form submitted successfully</div>

// Live region for content that updates
<div aria-live="polite" aria-atomic="true">
  {resultCount} results found
</div>

// Dialog (modal)
<div role="dialog" aria-modal="true" aria-labelledby="dialog-title">
  <h2 id="dialog-title">Confirm deletion</h2>
  ...
</div>

// Tab interface
<div role="tablist" aria-label="Settings sections">
  <button role="tab" aria-selected={active === "general"}>General</button>
  <button role="tab" aria-selected={active === "security"}>Security</button>
</div>
<div role="tabpanel">...</div>
```

### Required ARIA attributes

- `aria-label` or `aria-labelledby`: Every interactive element needs an
  accessible name.
- `aria-expanded`: Toggles (menus, accordions, dropdowns).
- `aria-current="page"`: Active navigation link.
- `aria-invalid` and `aria-describedby`: Form validation errors.
- `aria-hidden="true"`: Decorative elements that screen readers should skip.

## Keyboard Interaction

### Expected keyboard behavior

| Component  | Keys                                               |
| ---------- | -------------------------------------------------- |
| Button     | Enter, Space → activate                            |
| Link       | Enter → follow                                     |
| Menu       | Arrow keys → navigate, Escape → close              |
| Dialog     | Escape → close, Tab → cycle within                 |
| Tabs       | Arrow keys → switch tab, Tab → enter panel         |
| Combobox   | Arrow keys → navigate, Enter → select, Esc → close |
| Checkbox   | Space → toggle                                     |

### Focus management

```tsx
function Dialog({ isOpen, onClose, children }: DialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      previousFocus.current = document.activeElement as HTMLElement;
      dialogRef.current?.focus();
    } else {
      previousFocus.current?.focus(); // restore focus on close
    }
  }, [isOpen]);

  // Trap focus inside dialog
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") onClose();
    if (e.key === "Tab") {
      // implement focus trap logic
    }
  };

  if (!isOpen) return null;

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      tabIndex={-1}
      onKeyDown={handleKeyDown}
    >
      {children}
    </div>
  );
}
```

### Tab order

- Interactive elements follow the DOM order. Do not use `tabIndex > 0`.
- Use `tabIndex={0}` to make non-interactive elements focusable.
- Use `tabIndex={-1}` for elements that should be programmatically
  focusable but not in the tab order.

## Focus Management Patterns

### Skip links

```tsx
<a href="#main-content" className="skip-link">
  Skip to main content
</a>
```

CSS: visually hidden until focused.

### Focus on route change

In single-page apps, move focus to the main content heading when the
route changes:

```tsx
function useFocusOnRouteChange() {
  const location = useLocation();
  useEffect(() => {
    const heading = document.querySelector("h1");
    heading?.focus();
  }, [location.pathname]);
}
```

### Announce dynamic content

Use `aria-live` regions for content that changes without page reload:

```tsx
<div aria-live="polite" className="sr-only">
  {notification}
</div>
```

- `aria-live="polite"`: Announce when the user is idle.
- `aria-live="assertive"`: Announce immediately (use for errors only).

## Testing Accessibility

### In tests

```tsx
// Query by role — if it fails, the element lacks accessible semantics
screen.getByRole("button", { name: "Submit" });
screen.getByRole("heading", { level: 2, name: "Settings" });

// Check ARIA attributes
expect(screen.getByRole("textbox")).toHaveAttribute("aria-invalid", "true");
expect(screen.getByRole("tab")).toHaveAttribute("aria-selected", "true");

// Keyboard interaction
await user.tab();
expect(screen.getByRole("button")).toHaveFocus();
await user.keyboard("{Enter}");
```

### Automated tools

- `eslint-plugin-jsx-a11y`: Catches common issues at lint time.
- `axe-core` via `@axe-core/react` or `jest-axe`: Runtime accessibility
  checks in tests.
- Manual screen reader testing: VoiceOver (macOS), NVDA (Windows).
