# PostgreSQL Connection Pooling

## Why Pool Connections

PostgreSQL forks a new process per connection. Each connection consumes:
- ~10 MB of memory (RSS).
- A slot in `max_connections` (default 100).
- Kernel resources for the backend process.

Opening a connection takes 50-100ms (TCP handshake + authentication +
backend fork). Without pooling, every request pays this cost.

## Pool Sizing Formula

### Optimal pool size

The formula from the PostgreSQL wiki:

```
pool_size = (core_count * 2) + effective_spindle_count
```

For SSD-based systems (no spindles):

```
pool_size = (core_count * 2) + 1
```

Example: 4-core server with SSD = (4 * 2) + 1 = 9 connections.

### Common mistakes

- **Too large**: 100+ connections per application instance. PostgreSQL
  performance degrades beyond ~200 total connections due to lock contention
  and process scheduling.
- **Too small**: 1-2 connections. Creates a bottleneck where requests queue
  waiting for a connection.
- **Ignoring multiple instances**: 5 app instances with 20 connections each =
  100 total connections. Size per instance, not per application.

### Right-sizing process

1. Start with the formula result.
2. Monitor connection wait time (time spent waiting for a pool connection).
3. If wait time > 0 consistently, increase pool size by 2.
4. If connections are idle > 80% of the time, decrease pool size.
5. Never exceed `max_connections / number_of_instances`.

## PgBouncer vs Application Pool

### PgBouncer (external pooler)

Sits between the application and PostgreSQL. Multiplexes many client
connections onto fewer server connections.

```
App (100 connections) → PgBouncer (20 connections) → PostgreSQL
```

Advantages:
- Centralizes connection management across multiple applications.
- Reduces total PostgreSQL connections.
- Handles connection reuse when applications restart.
- Language-agnostic.

Disadvantages:
- Additional infrastructure to deploy and monitor.
- Some PostgreSQL features restricted in certain modes (prepared statements
  in transaction mode).

### Application pool (built-in)

Connection pool inside the application runtime (SQLAlchemy pool,
pgx pool, node-pg pool).

Advantages:
- No additional infrastructure.
- Simpler deployment.
- Full PostgreSQL feature support.

Disadvantages:
- Each application instance maintains its own pool.
- Cannot share connections between different applications.
- Pool is lost on application restart.

### When to use which

- **Single application, few instances**: Application pool is sufficient.
- **Multiple applications or many instances**: PgBouncer centralizes
  management and keeps total connections low.
- **Serverless / Lambda**: PgBouncer or RDS Proxy is essential — each
  invocation would otherwise open a new connection.

## Transaction vs Session Mode

### Session mode (PgBouncer default)

A server connection is assigned to a client for the entire session
(connect to disconnect).

- Supports all PostgreSQL features.
- Least connection savings — one client = one server connection.
- Use when applications hold long-lived connections.

### Transaction mode (recommended for most applications)

A server connection is assigned only for the duration of a transaction.
Between transactions, the connection returns to the pool.

- Maximum connection multiplexing.
- Restrictions: no prepared statements (unless using PgBouncer 1.21+
  with `max_prepared_statements`), no session-level SET commands, no
  LISTEN/NOTIFY.
- Use for web applications with short transactions.

### Statement mode

A server connection is assigned per SQL statement. Transactions spanning
multiple statements are not supported.

- Maximum sharing but very limited. Rarely appropriate.
- Only use for simple single-statement queries.

## Configuration Examples

### PgBouncer (pgbouncer.ini)

```ini
[databases]
myapp = host=127.0.0.1 port=5432 dbname=myapp

[pgbouncer]
pool_mode = transaction
max_client_conn = 200
default_pool_size = 20
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 3
server_idle_timeout = 300
```

### SQLAlchemy (Python)

```python
engine = create_engine(
    "postgresql://user:pass@host/db",
    pool_size=10,         # steady-state connections
    max_overflow=5,       # additional connections under load
    pool_timeout=30,      # seconds to wait for a connection
    pool_recycle=1800,    # recycle connections after 30 min
    pool_pre_ping=True,   # verify connections before use
)
```

### node-pg (Node.js)

```javascript
const pool = new Pool({
  max: 10,                // maximum connections
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
});
```

## Monitoring

Key metrics to track:
- **Active connections**: Currently executing queries.
- **Idle connections**: Connected but not executing.
- **Waiting clients**: Requests queued for a connection.
- **Connection errors**: Failed connection attempts.
- **Average query time**: Increasing times may indicate pool saturation.

```sql
-- Check current connections
select state, count(*)
from pg_stat_activity
where datname = 'myapp'
group by state;

-- Check connection limits
show max_connections;
select count(*) from pg_stat_activity;
```
