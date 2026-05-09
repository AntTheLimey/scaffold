# Interface Design Reference

## API Contract Principles

An API contract is a binding agreement between the producer and consumer. It
specifies what the consumer can send, what they will receive, and what errors
to expect. The contract exists before any implementation.

### Contract Components

Every endpoint must define:
- **Method and path**: `GET /api/v1/users/{id}`
- **Path parameters**: Name, type, constraints (e.g., `id: UUID`)
- **Query parameters**: Name, type, default, whether required
- **Request body schema**: Field names, types, nullability, validation rules
- **Response schema**: Field names, types, envelope structure
- **Error responses**: Status codes, error body structure, when each occurs
- **Authentication**: Required or public, what scopes/roles are needed

### Schema-First Design

Define the data shapes before writing any code. The schema is the source of
truth. Implementation must conform to the schema, not the other way around.

Benefits:
- Frontend and backend can develop in parallel against the schema.
- Tests can be generated from the schema.
- Breaking changes are visible as schema diffs.

Schema evolution rules:
- Adding a new optional field is backward-compatible.
- Adding a new required field is a breaking change.
- Removing a field is a breaking change.
- Changing a field's type is a breaking change.
- Renaming a field is a breaking change (it is a remove + add).

## REST Conventions

### Resource Naming
- Use nouns, not verbs: `/users` not `/getUsers`.
- Use plural: `/users` not `/user`.
- Use kebab-case for multi-word resources: `/user-profiles`.
- Nest for ownership: `/users/{id}/posts` (posts belonging to a user).
- Limit nesting to 2 levels: `/users/{id}/posts/{id}` is the maximum.

### HTTP Methods
- `GET`: Read. No side effects. Cacheable. Returns 200 with data or 404.
- `POST`: Create. Returns 201 with the created resource and Location header.
- `PUT`: Full replace. Client sends the entire resource. Returns 200.
- `PATCH`: Partial update. Client sends only changed fields. Returns 200.
- `DELETE`: Remove. Returns 204 with no body.

### Status Codes
- `200`: Success with body.
- `201`: Created. Include Location header.
- `204`: Success, no body (DELETE, some PUTs).
- `400`: Client sent invalid data. Body explains what is wrong.
- `401`: Not authenticated. The request lacks valid credentials.
- `403`: Authenticated but not authorized for this action.
- `404`: Resource does not exist.
- `409`: Conflict (e.g., duplicate email on registration).
- `422`: Semantically invalid (well-formed JSON but business rules violated).
- `500`: Server error. Never expose internal details.

### Error Response Structure

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": [
      {"field": "email", "issue": "already registered"}
    ]
  }
}
```

### Pagination

Use cursor-based pagination for large collections:

```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "abc123",
    "has_more": true
  }
}
```

Offset-based pagination (`?page=2&per_page=20`) is simpler but breaks when
items are inserted or deleted between pages.

## Common Interface Design Mistakes

- **Exposing internal IDs**: Use UUIDs externally even if the database uses
  auto-increment integers.
- **Leaking implementation details**: Error messages that include stack traces,
  SQL queries, or internal service names.
- **Inconsistent naming**: Mixing camelCase and snake_case in the same API.
  Pick one and enforce it.
- **Missing versioning**: Use URL versioning (`/api/v1/`) from day one. Adding
  it later is a breaking change.
- **God endpoints**: One endpoint that does everything based on query parameters.
  Split by resource and action.
