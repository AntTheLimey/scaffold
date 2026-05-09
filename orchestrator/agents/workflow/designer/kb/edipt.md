# EDIPT Design Thinking Framework

## Overview

EDIPT (Empathize, Define, Ideate, Prototype, Test) is a structured approach to
design that keeps user needs at the center of every decision. When specifying
UI/UX for an automated pipeline, apply each phase as a thinking step, not a
process to execute.

## Empathize

Understand who uses this interface and what they need from it.

Questions to answer before designing:
- Who is the primary user? (Role, technical skill level, frequency of use.)
- What problem are they solving when they reach this interface?
- What are they doing immediately before and after using this feature?
- What frustrations do they have with similar interfaces?
- What is their environment? (Desktop, mobile, noisy, distracted, low bandwidth.)

In an automated pipeline, empathy data comes from:
- The spec's user descriptions and personas.
- Acceptance criteria that mention user actions.
- The project's CLAUDE.md if it describes users.

When empathy data is missing, default to: "A moderately technical user on a
desktop browser, somewhat distracted, using this feature a few times per week."
This avoids designing for power users while excluding beginners.

## Define

Synthesize empathy findings into specific design problems.

Structure the problem as: "[User type] needs a way to [accomplish goal] because
[reason], but currently [obstacle]."

Good problem statement: "A project manager needs a way to see task status at
a glance because they check progress 10+ times daily, but currently must open
each task individually."

Bad problem statement: "The dashboard needs to look better." (No user, no goal,
no obstacle.)

Constraints to capture:
- Accessibility requirements (always WCAG 2.1 AA minimum).
- Performance requirements (page load, interaction response time).
- Content requirements (what data must be shown, what is optional).
- Device requirements (responsive breakpoints, touch support).

## Ideate

Generate multiple approaches before committing to one.

For each feature, briefly consider at least two layout approaches:
1. The conventional approach (how most similar apps solve this).
2. An alternative that optimizes for the specific user context.

Evaluation criteria:
- Learnability: Can a new user figure this out without documentation?
- Efficiency: Can a frequent user complete the task with minimal steps?
- Error tolerance: Does the design prevent errors or make recovery easy?
- Accessibility: Does the approach work with assistive technology?

Select the approach that best balances these criteria for the defined user.

## Prototype

In a specification context, the prototype is the detailed component description.
It is not a visual mockup — it is a precise enough description that a developer
can build it without design ambiguity.

Specification checklist:
- Layout: Spatial arrangement with sizing and spacing.
- Content: What text, data, and media appears in each area.
- States: Every visual state (default, loading, error, empty, success, disabled).
- Interactions: Every user action and its response.
- Responsive behavior: Layout changes at each breakpoint.
- Accessibility: ARIA roles, keyboard navigation, screen reader behavior.

## Test

Define how the design will be validated against user needs.

For each component, specify:
- What acceptance criteria map to UI behavior?
- What would a usability test check? (Even if not run, this thinking improves
  the spec.)
- What are the edge cases? (Very long text, no data, slow loading, error state.)

Common test scenarios to always consider:
- First-time use: User has no prior context. Is the interface self-explanatory?
- Power use: User performs this action 100 times. Is it efficient?
- Error recovery: Something goes wrong. Can the user understand what happened
  and fix it?
- Accessibility: Can a keyboard-only user complete the task? Does a screen
  reader convey the content meaningfully?

## Applying EDIPT in the Pipeline

When the designer node receives a task:
1. Empathize: Extract user context from the spec and acceptance criteria.
2. Define: State the design problem in one sentence.
3. Ideate: Briefly consider two approaches, select one with rationale.
4. Prototype: Write the full component specification.
5. Test: Define validation criteria aligned with acceptance criteria.

This takes 1-2 sentences for steps 1-3, then the bulk of the output is step 4.
Step 5 maps to the acceptance criteria in the task.
