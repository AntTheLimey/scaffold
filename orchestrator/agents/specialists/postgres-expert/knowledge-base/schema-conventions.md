# PostgreSQL Schema Conventions

## Naming

### Tables

- snake_case, plural: `user_accounts`, `order_items`, `audit_logs`.
- Join tables: alphabetical order of the two tables:
  `project_users` not `user_projects`.
- No prefixes: `users` not `tbl_users`.

### Columns

- snake_case: `created_at`, `first_name`, `is_active`.
- Foreign keys: `{referenced_table_singular}_id` — `user_id`, `order_id`.
- Boolean columns: `is_` or `has_` prefix — `is_active`, `has_verified_email`.
- Timestamps: `_at` suffix — `created_at`, `updated_at`, `deleted_at`.

### Indexes

- Regular: `idx_{table}_{column(s)}` — `idx_users_email`.
- Unique: `uniq_{table}_{column(s)}` — `uniq_users_email`.
- Partial: `idx_{table}_{column}_{condition}` — `idx_orders_status_active`.

### Constraints

- Primary key: `pk_{table}` — `pk_users`.
- Foreign key: `fk_{table}_{referenced_table}` — `fk_orders_users`.
- Check: `chk_{table}_{description}` — `chk_users_email_format`.

## Column Types

### Text

- `text` for variable-length strings. No performance difference from
  `varchar(n)` in PostgreSQL.
- `varchar(n)` only when a hard length limit is a business rule (e.g.,
  ISO country codes: `varchar(2)`).
- Never `char(n)` — it pads with spaces.

### Numbers

- `integer` (4 bytes) for most counters and IDs.
- `bigint` (8 bytes) for IDs that may exceed 2 billion or timestamps.
- `numeric(precision, scale)` for money and exact decimal values.
  Never `float` or `real` for money.
- `smallint` for small enumerations or flags.

### Timestamps

- Always `timestamptz` (with time zone), never `timestamp` (without).
- Store in UTC. Let the application layer handle display conversion.
- Default: `default now()` for creation timestamps.

### UUIDs

- `uuid` type with `gen_random_uuid()` default (PostgreSQL 13+).
- Use when IDs are exposed externally or generated client-side.
- Use `bigint generated always as identity` when IDs are internal-only
  (better index performance, smaller storage).

### JSON

- `jsonb` for structured data (supports indexing and operators).
- Never `json` (stored as text, no indexing).
- Use columns for frequently queried fields. Use jsonb for metadata
  or configuration that varies per row.

### Enums

- PostgreSQL `enum` types for stable, rarely-changing value sets.
- `text` with a check constraint for sets that change with deployments.
- Consider a lookup table for sets managed by application users.

## Constraints

### Primary keys

```sql
create table users (
    id bigint generated always as identity primary key
);

-- or with UUID
create table users (
    id uuid default gen_random_uuid() primary key
);
```

### Foreign keys

```sql
alter table orders
    add constraint fk_orders_users
    foreign key (user_id) references users (id)
    on delete restrict;  -- prevent deleting users with orders
```

Always specify `on delete` behavior:
- `restrict`: Prevent deletion of referenced row (default, safest).
- `cascade`: Delete child rows when parent is deleted.
- `set null`: Set foreign key to null when parent is deleted.

### Not null

Default to `not null`. Allow null only when the absence of a value has
specific business meaning distinct from empty string or zero.

### Check constraints

```sql
alter table users
    add constraint chk_users_email_format
    check (email ~* '^[^@]+@[^@]+\.[^@]+$');

alter table orders
    add constraint chk_orders_positive_total
    check (total > 0);
```

## Standard Columns

Every table should include:

```sql
create table example (
    id bigint generated always as identity primary key,
    -- domain columns here
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
```

For soft deletes:

```sql
    deleted_at timestamptz  -- null means not deleted
```

Create a partial index for active records:

```sql
create index idx_example_active on example (id) where deleted_at is null;
```

## Migration Safety

- Never drop a column in the same release that stops writing to it.
  Deprecate first, then remove in the next release.
- Add new columns as nullable or with a default. Adding a `not null`
  column without a default locks the table for a full rewrite.
- Create indexes concurrently: `create index concurrently` to avoid
  blocking writes.
- Test migrations against a copy of production data volume. A migration
  that runs in 1 second on 100 rows may take 30 minutes on 10 million.
