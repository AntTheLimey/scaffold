# Go Concurrency

## Goroutines

### Launching goroutines safely

Always handle the goroutine lifecycle. Never fire-and-forget:

```go
// BAD: goroutine leak — no way to stop it
go processForever()

// GOOD: controlled lifecycle
ctx, cancel := context.WithCancel(context.Background())
defer cancel()

go func() {
    for {
        select {
        case <-ctx.Done():
            return
        case item := <-ch:
            process(item)
        }
    }
}()
```

### Rules

- Every goroutine must have a termination condition.
- Pass `context.Context` to goroutines that do I/O or may run long.
- Never share variables between goroutines without synchronization.
- Use `go vet` and `go test -race` to detect data races.

## Channels

### Directional channels

```go
func producer(out chan<- int) { // send-only
    out <- 42
    close(out)
}

func consumer(in <-chan int) { // receive-only
    for val := range in {
        fmt.Println(val)
    }
}
```

### Buffered vs unbuffered

- **Unbuffered** (`make(chan int)`): Sender blocks until receiver reads.
  Use for synchronization.
- **Buffered** (`make(chan int, 100)`): Sender blocks only when buffer is
  full. Use for decoupling producer/consumer speeds.

### Select statement

```go
select {
case msg := <-msgCh:
    handle(msg)
case err := <-errCh:
    handleError(err)
case <-ctx.Done():
    return ctx.Err()
case <-time.After(5 * time.Second):
    return errors.New("timeout")
}
```

### Channel closing

- Only the sender closes a channel. Never close from the receiver side.
- Closing a nil channel panics. Closing an already-closed channel panics.
- Use `val, ok := <-ch` to detect closed channels.
- `range ch` automatically stops when the channel is closed.

## sync Primitives

### sync.Mutex

```go
type Counter struct {
    mu    sync.Mutex
    count int
}

func (c *Counter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count++
}

func (c *Counter) Value() int {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.count
}
```

Use `sync.RWMutex` when reads greatly outnumber writes.

### sync.WaitGroup

```go
var wg sync.WaitGroup
for _, item := range items {
    wg.Add(1)
    go func(item Item) {
        defer wg.Done()
        process(item)
    }(item)
}
wg.Wait()
```

Always call `wg.Add` before launching the goroutine, not inside it.

### sync.Once

```go
var (
    instance *Client
    once     sync.Once
)

func GetClient() *Client {
    once.Do(func() {
        instance = &Client{} // runs exactly once
    })
    return instance
}
```

## errgroup

Coordinated goroutines with error propagation:

```go
import "golang.org/x/sync/errgroup"

g, ctx := errgroup.WithContext(ctx)

for _, url := range urls {
    url := url // capture loop variable
    g.Go(func() error {
        return fetch(ctx, url)
    })
}

if err := g.Wait(); err != nil {
    // first error from any goroutine
    return fmt.Errorf("fetch failed: %w", err)
}
```

Use `errgroup.SetLimit(n)` to bound concurrency.

## Context

### Propagation rules

- `context.Context` is the first parameter of every function that does I/O.
- Never store contexts in structs. Pass them as function arguments.
- Use `context.WithTimeout` or `context.WithDeadline` for bounded operations.
- Check `ctx.Err()` before starting expensive work.

```go
func fetchData(ctx context.Context, id string) (Data, error) {
    if err := ctx.Err(); err != nil {
        return Data{}, err // already cancelled
    }
    req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
    if err != nil {
        return Data{}, fmt.Errorf("create request: %w", err)
    }
    // ...
}
```

### Context values

Use sparingly. Only for request-scoped data that crosses API boundaries
(request ID, trace ID). Never for function parameters.

## Race Conditions

- Read-modify-write without locks (counter increment, map update).
- Checking and acting without locks (check-then-act).
- Sharing slices or maps between goroutines.

Detection: `go test -race ./...` — run in CI. Every race is a bug.

Prevention: prefer channels over shared memory. Protect shared memory
with `sync.Mutex`. Use `sync.Map` only for append-only caches. Prefer
immutable data — pass copies, not references, to goroutines.
