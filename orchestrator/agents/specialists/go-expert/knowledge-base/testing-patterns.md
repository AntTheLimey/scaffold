# Go Testing Patterns

## Table-Driven Tests

The standard Go testing pattern. Define inputs and expected outputs in a slice,
iterate with subtests:

```go
func TestParseConfig(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    Config
        wantErr bool
    }{
        {
            name:  "valid yaml",
            input: "port: 8080\nhost: localhost",
            want:  Config{Port: 8080, Host: "localhost"},
        },
        {
            name:    "empty input",
            input:   "",
            wantErr: true,
        },
        {
            name:    "malformed yaml",
            input:   ": invalid: :",
            wantErr: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ParseConfig([]byte(tt.input))
            if tt.wantErr {
                if err == nil {
                    t.Fatal("expected error, got nil")
                }
                return
            }
            if err != nil {
                t.Fatalf("unexpected error: %v", err)
            }
            if got != tt.want {
                t.Errorf("got %+v, want %+v", got, tt.want)
            }
        })
    }
}
```

### When to use table-driven tests

- Testing the same function with multiple input/output combinations.
- Boundary value testing (0, 1, max, max+1).
- Error case enumeration.

### When NOT to use table-driven tests

- Tests that need significantly different setup for each case.
- Tests where the assertion logic varies per case.
- Integration tests with complex state transitions.

## testify vs Standard Library

### Standard library (preferred for simplicity)

```go
if got != want {
    t.Errorf("Get(%q) = %v, want %v", key, got, want)
}
```

### testify (when project already uses it)

```go
import "github.com/stretchr/testify/assert"

assert.Equal(t, want, got)
assert.NoError(t, err)
assert.ErrorIs(t, err, ErrNotFound)
assert.Contains(t, output, "expected substring")
```

Follow whichever the project uses. Do not mix in the same file.

## Test Helpers

```go
// t.Helper() marks a function as a test helper.
// Failure messages report the caller's line, not the helper's.
func mustParseURL(t *testing.T, raw string) *url.URL {
    t.Helper()
    u, err := url.Parse(raw)
    if err != nil {
        t.Fatalf("failed to parse URL %q: %v", raw, err)
    }
    return u
}
```

### Temporary directories

```go
func TestWriteFile(t *testing.T) {
    dir := t.TempDir() // automatically cleaned up
    path := filepath.Join(dir, "output.txt")
    err := WriteFile(path, "content")
    if err != nil {
        t.Fatal(err)
    }
    // verify file contents
}
```

## httptest

For testing HTTP handlers and clients:

```go
// Testing a handler
func TestHealthHandler(t *testing.T) {
    req := httptest.NewRequest("GET", "/health", nil)
    w := httptest.NewRecorder()

    HealthHandler(w, req)

    resp := w.Result()
    if resp.StatusCode != http.StatusOK {
        t.Errorf("status = %d, want %d", resp.StatusCode, http.StatusOK)
    }
}

// Testing a client with a fake server
func TestClientFetch(t *testing.T) {
    srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(200)
        w.Write([]byte(`{"status":"ok"}`))
    }))
    defer srv.Close()

    client := NewClient(srv.URL)
    result, err := client.Fetch()
    // assert result
}
```

## Golden Files

For complex output (JSON, HTML, large strings), compare against stored files:

```go
func TestRender(t *testing.T) {
    got := Render(input)
    golden := filepath.Join("testdata", t.Name()+".golden")

    if *update {
        os.WriteFile(golden, []byte(got), 0o644)
    }

    want, err := os.ReadFile(golden)
    if err != nil {
        t.Fatal(err)
    }
    if got != string(want) {
        t.Errorf("output mismatch, run with -update to refresh golden file")
    }
}
```

Store golden files in `testdata/` directory (ignored by `go build`).

## Anti-Patterns

- **Testing unexported functions**: Test through the public API. If you must
  test internals, use `_test.go` in the same package (not `_test` package).
- **Global test state**: Each test function or subtest must be independent.
  Use `t.Cleanup()` for teardown.
- **Ignoring the race detector**: Always run `go test -race` in CI.
  Never silence race conditions.
- **Skipping error checks in tests**: Even in tests, handle errors explicitly.
  Use `t.Fatal(err)` to fail fast on unexpected errors.
