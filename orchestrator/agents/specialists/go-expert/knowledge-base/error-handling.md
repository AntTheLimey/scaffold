# Go Error Handling

## Error Wrapping

Add context when propagating errors up the call stack:

```go
result, err := db.Query(ctx, sql)
if err != nil {
    return fmt.Errorf("fetch users: %w", err)
}
```

Rules:
- Use `%w` verb to wrap (preserves the original error for `errors.Is/As`).
- Use `%v` verb when you intentionally want to break the error chain.
- Error messages are lowercase, no trailing punctuation.
- Prefix with the operation that failed: `"parse config: %w"`.

## Sentinel Errors

Package-level errors for expected failure conditions:

```go
var (
    ErrNotFound     = errors.New("not found")
    ErrUnauthorized = errors.New("unauthorized")
    ErrConflict     = errors.New("conflict")
)
```

Naming convention: `Err` prefix + condition.

Check with `errors.Is`:

```go
if errors.Is(err, ErrNotFound) {
    w.WriteHeader(http.StatusNotFound)
    return
}
```

## Custom Error Types

For errors that carry structured data:

```go
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation failed on %s: %s", e.Field, e.Message)
}

// Usage
return &ValidationError{Field: "email", Message: "invalid format"}
```

Check with `errors.As`:

```go
var valErr *ValidationError
if errors.As(err, &valErr) {
    log.Printf("field %s: %s", valErr.Field, valErr.Message)
}
```

## errors.Is and errors.As

### errors.Is — checks if any error in the chain matches a target value

```go
// Works through wrapping layers
err := fmt.Errorf("query failed: %w", ErrNotFound)
errors.Is(err, ErrNotFound) // true
```

### errors.As — extracts a specific error type from the chain

```go
var pathErr *os.PathError
if errors.As(err, &pathErr) {
    log.Printf("path: %s, op: %s", pathErr.Path, pathErr.Op)
}
```

Never use string comparison (`err.Error() == "..."`) for error checking.
Never use type assertions (`err.(*MyError)`) — use `errors.As` instead.

## Panic vs Return Error

### Use error returns for:
- Expected failures (file not found, invalid input, network timeout).
- Conditions the caller can handle or retry.
- Any library or package code.

### Use panic only for:
- Programming errors that indicate a bug (index out of bounds, nil pointer
  that should never be nil).
- Unrecoverable states in `main()` during startup (cannot connect to
  required database).
- In test helpers where failure means the test setup is broken.

### Recovering from panics

```go
func safeHandler(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if r := recover(); r != nil {
                log.Printf("panic recovered: %v", r)
                http.Error(w, "internal error", 500)
            }
        }()
        next.ServeHTTP(w, r)
    })
}
```

Only recover at top-level boundaries (HTTP middleware, goroutine entry points).
Never silently swallow panics.

## Error Handling Patterns

### Multi-error collection

```go
var errs []error
for _, item := range items {
    if err := process(item); err != nil {
        errs = append(errs, fmt.Errorf("item %s: %w", item.ID, err))
    }
}
if len(errs) > 0 {
    return errors.Join(errs...)
}
```

### Deferred cleanup with error handling

```go
func writeFile(path string, data []byte) (retErr error) {
    f, err := os.Create(path)
    if err != nil {
        return fmt.Errorf("create file: %w", err)
    }
    defer func() {
        if closeErr := f.Close(); closeErr != nil && retErr == nil {
            retErr = fmt.Errorf("close file: %w", closeErr)
        }
    }()
    _, err = f.Write(data)
    if err != nil {
        return fmt.Errorf("write data: %w", err)
    }
    return nil
}
```

### Early return pattern

```go
func process(input string) (Result, error) {
    if input == "" {
        return Result{}, errors.New("empty input")
    }

    parsed, err := parse(input)
    if err != nil {
        return Result{}, fmt.Errorf("parse: %w", err)
    }

    validated, err := validate(parsed)
    if err != nil {
        return Result{}, fmt.Errorf("validate: %w", err)
    }

    return transform(validated), nil
}
```

Keep the happy path unindented. Error handling exits early.
