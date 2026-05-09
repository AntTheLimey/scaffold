# Technical Writing Style Guide

## Principles

### Clarity over cleverness

- Use simple, direct language. "Start the server" not "Spin up the server."
- One idea per sentence. If a sentence has "and" or "but," consider splitting.
- Active voice: "The function returns a list" not "A list is returned."
- Present tense: "This command creates a file" not "This command will create."

### Audience awareness

- **User documentation**: Assume the reader knows their programming language
  but not your project. Explain project-specific concepts.
- **API reference**: Assume the reader is a developer integrating your API.
  Include types, errors, and edge cases.
- **Contributor guide**: Assume the reader can code but does not know your
  project's conventions.

### Precision

- Specific over vague: "Returns a 404 status code" not "Returns an error."
- Exact commands over descriptions: Show `npm install` not "Install the
  dependencies."
- Name things correctly: Use the exact function name, config key, or CLI flag.

## Document Structure

### README pattern

```markdown
# Project Name

One sentence describing what this project does.

## Quick start

Minimal steps to get running. 3-5 commands maximum.

## Installation

Full installation instructions with prerequisites.

## Usage

Most common use cases with examples.

## Configuration

Available settings with types, defaults, and examples.

## Contributing

How to set up the development environment and submit changes.

## License

License type and link to full text.
```

### Guide structure

```markdown
# Guide title

Brief introduction: what this guide covers and who it is for.

## Prerequisites

What the reader needs before starting.

## Steps

### Step 1: First thing

Explanation, then command, then expected output.

### Step 2: Second thing

...

## Troubleshooting

Common problems and solutions.

## Next steps

Links to related guides or advanced topics.
```

## Markdown Conventions

### Headings

- ATX-style (`#` prefix), not Setext (underline).
- Sentence case: "Getting started" not "Getting Started."
- No trailing punctuation in headings.
- One blank line before and after headings.
- Do not skip heading levels (h1 then h3).

### Code blocks

- Always specify the language: ` ```python `, ` ```bash `, ` ```json `.
- Use `bash` for shell commands, not `sh` or `shell`.
- Commands show `$` prompt only when distinguishing input from output.
- Include expected output when the reader needs to verify success.

```bash
$ npm test
# Expected: "All tests passed"
```

### Links

- Inline for one-off references: `[text](url)`.
- Reference-style for repeated links:

```markdown
See the [configuration guide][config] for details.

[config]: ./docs/configuration.md
```

- Relative paths for internal docs. Absolute URLs for external resources.

### Lists

- Unordered lists use `-` (not `*` or `+`).
- Ordered lists use `1.` for all items (auto-numbered by Markdown).
- Nested lists indent by 2 or 4 spaces (match project convention).
- List items that are full sentences end with a period.
- List items that are fragments do not end with a period.

### Tables

```markdown
| Column 1 | Column 2 | Column 3 |
| -------- | -------- | -------- |
| value    | value    | value    |
```

Use tables for structured comparisons. Do not use tables for layout.

## Code Examples

### Rules for examples

- Every example must be complete and runnable. No `...` elisions that
  break copy-paste.
- Use realistic values: `user@example.com` not `foo@bar.baz`.
- Show the import/require statement if the reader needs it.
- Include error handling when relevant to the documented feature.
- Show output or expected result after the code.

### Good example

```python
from mylib import validate_email

result = validate_email("user@example.com")
print(result)  # True

result = validate_email("not-an-email")
print(result)  # False
```

### Bad example

```python
# Call the function
validate_email(...)  # returns True or False
```

Why this is bad: Not runnable. No import. Elision breaks copy-paste.
No actual input or output.

## API Documentation

### Function documentation pattern

Include: description, parameters table (name, type, required, description),
return type, throws, and a runnable example.

### REST API documentation pattern

Include: method + path, description, request body table, response status,
example response, and error codes with descriptions.

## Tone

- Professional but approachable. Not academic, not casual.
- No filler words: "basically," "simply," "just," "obviously."
- No assumptions about ease: "simply run" implies the reader should
  find it easy, which is unhelpful if they are stuck.
- Do not apologize: "Unfortunately, this is not supported" — just state
  the limitation and the alternative.
