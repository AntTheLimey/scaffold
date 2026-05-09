# Responsive Design Reference

## Mobile-First Approach

Design for the smallest screen first, then add complexity for larger screens.

Rationale:
- Forces prioritization: small screens have less space, so only essential
  content makes the cut.
- Progressive enhancement: adding features for larger screens is easier than
  removing them for smaller ones.
- Performance: mobile devices typically have slower connections and less
  processing power.

Process:
1. Define the content hierarchy for mobile (what is most important?).
2. Lay out content in a single column at the mobile breakpoint.
3. Add multi-column layouts and additional content at larger breakpoints.

## Breakpoints

Standard breakpoints (use as defaults unless the project specifies others):

| Name | Width | Typical Devices |
|---|---|---|
| Mobile | < 768px | Phones (portrait and landscape) |
| Tablet | 768px - 1024px | Tablets, small laptops |
| Desktop | > 1024px | Laptops, desktop monitors |

Content-based breakpoints: Rather than designing for device categories, set
breakpoints where the content breaks. If a paragraph becomes too wide to read
comfortably (over ~75 characters per line), add a breakpoint there.

Do not design for specific devices. Device sizes change yearly. Design for
content at fluid widths.

## Layout Patterns

### Single Column (Mobile Default)
All content stacks vertically. Navigation collapses to a hamburger menu or
bottom tab bar. This is the base layout.

### Sidebar (Tablet+)
Navigation or filters move to a persistent sidebar. Main content occupies the
remaining width. Sidebar width is fixed; main content is fluid.

### Multi-Column Grid (Desktop)
Content arranges in 2-4 columns. Use a grid system with consistent gutters.
Cards and tiles work well in grids. Lists and forms generally stay single-column
even on desktop.

### Responsive Tables
Tables are problematic on mobile. Options:
- **Horizontal scroll**: Wrap the table in a scrollable container. Add a visual
  indicator that scrolling is available.
- **Card transformation**: Each row becomes a card with label-value pairs stacked
  vertically.
- **Priority columns**: Show essential columns on mobile, reveal additional
  columns as width increases.

## Touch vs Mouse Considerations

### Touch Interactions
- Tap targets: minimum 44x44px with 8px spacing between adjacent targets.
- Swipe: use for navigation between pages/cards. Never as the only way to
  access a destructive action (too easy to trigger accidentally).
- Long press: avoid or use only as a shortcut. It is not discoverable.
- Pinch/zoom: do not disable. Users with low vision depend on it.

### Mouse Interactions
- Hover states: Provide visual feedback on hover, but never hide essential
  information or controls behind hover. Mobile has no hover.
- Right-click menus: Only use as shortcuts. All actions must be accessible
  without right-click.
- Tooltips: On desktop, show on hover. On mobile, show on tap or replace with
  an info icon that opens an overlay.

### Converged Approach
Design interactions that work on both input types:
- Click/tap both trigger the same action.
- Hover-revealed content has a click/tap alternative.
- Drag-and-drop has a button-based alternative (e.g., move up/down buttons).

## Flexible Layouts

### Fluid Sizing
- Use relative units (%, rem, em, vw) instead of fixed pixels for layout.
- Set max-width on text containers to maintain readability (~75 characters).
- Use min-width to prevent elements from collapsing too small.

### Images
- Images should scale with their container (max-width: 100%).
- Provide multiple resolutions for different screen densities.
- Use aspect-ratio containers to prevent layout shift while images load.
- Decorative images can be hidden on mobile to save bandwidth.

### Typography
- Base font size: 16px minimum. Never go below this.
- Scale headings proportionally. On mobile, reduce heading sizes less
  aggressively (a desktop h1 at 36px might be 28px on mobile, not 18px).
- Line height: 1.4-1.6 for body text. Tighter for headings.
- Line length: 50-75 characters for optimal readability.

### Spacing
- Use a spacing scale (e.g., 4px, 8px, 12px, 16px, 24px, 32px, 48px).
- Reduce spacing on mobile: what is 32px on desktop might be 16px on mobile.
- Consistent spacing within components; larger spacing between components.

## Common Responsive Mistakes

- **Hidden content on mobile**: If content is important enough to exist, it is
  important enough to show on mobile. Hiding it creates a second-class experience.
- **Identical layout scaled down**: Simply shrinking a desktop layout to fit
  mobile creates unusable interfaces. Redesign the layout for each breakpoint.
- **Fixed-width elements**: Any element with a fixed pixel width will eventually
  overflow on a small screen.
- **Hover-only interactions**: ~50% of web traffic is mobile. Hover does not
  exist on touchscreens. Every hover interaction needs a touch alternative.
- **Ignoring landscape**: Phones in landscape orientation have wide, short
  viewports. Tall fixed headers can consume most of the screen.
