# Accessibility Reference (WCAG 2.1 AA)

## Core Requirements

WCAG 2.1 AA is the baseline. Every UI specification must satisfy these
requirements. Non-compliance is a defect, not a preference.

## Perceivable

### Text Alternatives
- Every non-text element (image, icon, chart) has a text alternative.
- Decorative images use empty alt text (`alt=""`) so screen readers skip them.
- Complex images (charts, diagrams) have both short alt text and a longer
  description available.

### Color Contrast
- Normal text (under 18pt or 14pt bold): minimum 4.5:1 contrast ratio.
- Large text (18pt+ or 14pt+ bold): minimum 3:1 contrast ratio.
- UI components and graphical objects: minimum 3:1 contrast ratio against
  adjacent colors.
- Never use color as the sole means of conveying information. Pair color with
  text, icons, or patterns.

### Content Adaptability
- Content is meaningful when linearized (read in DOM order).
- Do not use tables for layout. Tables are for tabular data.
- Use semantic heading levels (h1-h6) in order. Do not skip levels.

### Time-Based Media
- Video has captions.
- Audio has transcripts.
- Autoplay is disabled or has a pause control within the first element.

## Operable

### Keyboard Navigation
- Every interactive element is reachable via Tab key.
- Tab order follows visual layout (left-to-right, top-to-bottom for LTR).
- Focus is visible: a clear outline or highlight on the focused element.
- No keyboard traps: the user can always Tab away from any element.
- Custom widgets implement expected keyboard patterns:
  - Buttons: Enter and Space to activate.
  - Links: Enter to follow.
  - Dropdowns: Arrow keys to navigate, Enter to select, Escape to close.
  - Modals: Tab cycles within the modal. Escape closes it. Focus returns to
    the trigger element on close.

### Touch Targets
- Minimum 44x44px for all interactive elements on touch devices.
- Adjacent targets have sufficient spacing to prevent accidental activation.

### Timing
- No time limits on user actions unless essential (e.g., auction bidding).
- If a timeout exists, warn the user 20 seconds before and offer extension.
- No content flashes more than 3 times per second.

## Understandable

### Readable
- Page language is declared in the HTML lang attribute.
- Abbreviations are defined on first use.
- Reading level is appropriate for the audience (avoid jargon when possible).

### Predictable
- Navigation is consistent across pages.
- Components that look the same behave the same.
- Focus changes do not trigger unexpected actions.
- Form submission requires explicit user action (a button click), not automatic
  submission on field change.

### Input Assistance
- Every form field has a visible label. Placeholder text alone is insufficient.
- Required fields are indicated before the user submits.
- Error messages identify the field, describe the error, and suggest correction.
- Error messages appear near the field, not only at the top of the form.
- Form validation does not rely solely on color (red border). Include an icon
  or text indicator.

## Robust

### Semantic HTML
- Use native HTML elements for their intended purpose: `<button>` for actions,
  `<a>` for navigation, `<input>` for data entry.
- Custom widgets that replace native elements must implement full ARIA semantics
  and keyboard behavior.
- Validate HTML. Invalid markup breaks assistive technology.

### ARIA Usage
- First rule of ARIA: do not use ARIA if a native HTML element does the job.
- ARIA roles must match behavior. A `role="button"` element must respond to
  Enter and Space, handle focus, and be in the tab order.
- Use `aria-label` or `aria-labelledby` when a visible label is not sufficient.
- Use `aria-live` regions for dynamic content updates that should be announced.
  Polite for non-urgent, assertive for critical (use sparingly).
- Use `aria-expanded`, `aria-selected`, `aria-checked` to communicate state
  to assistive technology.
- Test ARIA with an actual screen reader if possible. ARIA misuse is worse
  than no ARIA.

## Specification Checklist

When specifying a UI component, check:

1. Can every interactive element be reached and operated by keyboard alone?
2. Does every image/icon have appropriate alt text?
3. Do all color combinations meet contrast requirements?
4. Does every form field have a visible label?
5. Are all states (loading, error, empty) accessible?
6. Does the component announce dynamic changes to screen readers?
7. Is the tab order logical?
8. Are touch targets large enough?
