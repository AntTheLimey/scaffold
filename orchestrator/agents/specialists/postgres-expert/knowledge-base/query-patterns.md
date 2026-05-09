# PostgreSQL Query Patterns

## JOINs

### JOIN types

```sql
-- INNER JOIN: rows that match in both tables
select u.name, o.total
from users u
join orders o on o.user_id = u.id;

-- LEFT JOIN: all rows from left table, matched rows from right (or null)
select u.name, o.total
from users u
left join orders o on o.user_id = u.id;

-- Use LEFT JOIN when you need rows even without matches (e.g., users
-- without orders). Use INNER JOIN when unmatched rows are meaningless.
```

### JOIN performance

- Always JOIN on indexed columns. Foreign key columns should have indexes.
- Prefer specific column selection over `select *`.
- Filter early: put conditions in `WHERE` (not `HAVING`) when possible.
- For large result sets, consider whether a subquery or CTE is more readable
  without sacrificing performance.

## Common Table Expressions (CTEs)

### Readable multi-step queries

```sql
with active_users as (
    select id, name, email
    from users
    where is_active = true
      and last_login_at > now() - interval '30 days'
),
user_order_totals as (
    select u.id, u.name, sum(o.total) as total_spent
    from active_users u
    join orders o on o.user_id = u.id
    where o.created_at > now() - interval '90 days'
    group by u.id, u.name
)
select name, total_spent
from user_order_totals
where total_spent > 100
order by total_spent desc;
```

### Recursive CTEs

For tree structures (categories, org charts, comment threads):

```sql
with recursive category_tree as (
    -- base case: root categories
    select id, name, parent_id, 0 as depth
    from categories
    where parent_id is null

    union all

    -- recursive case: children
    select c.id, c.name, c.parent_id, ct.depth + 1
    from categories c
    join category_tree ct on ct.id = c.parent_id
)
select * from category_tree order by depth, name;
```

Always add a depth limit to prevent infinite recursion on cyclic data.

### CTE materialization

PostgreSQL 12+ can inline CTEs as subqueries for better optimization.
Force materialization with `as materialized (...)` when you want to
compute the CTE exactly once. Force inlining with `as not materialized (...)`
when the planner should optimize across the CTE boundary.

## Window Functions

### Row numbering and ranking

```sql
-- Number rows within each partition
select
    name,
    department,
    salary,
    row_number() over (partition by department order by salary desc) as rank
from employees;

-- Get top N per group
select * from (
    select *, row_number() over (
        partition by department order by salary desc
    ) as rn
    from employees
) ranked
where rn <= 3;
```

### Running totals and moving averages

```sql
select
    date,
    amount,
    sum(amount) over (order by date) as running_total,
    avg(amount) over (
        order by date
        rows between 6 preceding and current row
    ) as moving_avg_7day
from daily_revenue;
```

### Lead and lag

```sql
select
    date,
    amount,
    amount - lag(amount) over (order by date) as daily_change,
    lead(amount) over (order by date) as next_day_amount
from daily_revenue;
```

## Pagination

### Offset-based (simple but slow for deep pages)

```sql
select id, name, created_at
from users
order by created_at desc, id desc
limit 20 offset 100;
```

Problem: PostgreSQL must scan and discard 100 rows before returning 20.
Degrades linearly with page depth.

### Cursor-based (recommended for large datasets)

```sql
-- First page
select id, name, created_at
from users
order by created_at desc, id desc
limit 20;

-- Next page (using last row's values as cursor)
select id, name, created_at
from users
where (created_at, id) < ('2024-01-15 10:30:00+00', 12345)
order by created_at desc, id desc
limit 20;
```

Requires a unique, ordered cursor (composite of `created_at` + `id`).
Constant performance regardless of page depth.

## EXPLAIN ANALYZE

### Reading query plans

```sql
explain analyze
select u.name, count(o.id) as order_count
from users u
left join orders o on o.user_id = u.id
group by u.name;
```

Key metrics:
- **Actual time**: Real execution time in milliseconds.
- **Rows**: Actual vs estimated row count. Large discrepancies indicate
  stale statistics (`ANALYZE` the table).
- **Seq Scan**: Full table scan. Acceptable for small tables (<10K rows).
  Add an index for large tables.
- **Index Scan**: Uses an index. Expected for filtered queries.
- **Hash Join** vs **Nested Loop**: Hash join is better for large result
  sets. Nested loop is better when the inner side returns few rows.
- **Sort**: External sort (on disk) is slow. Consider adding an index
  that matches the sort order.

### When to worry

- Estimated rows differ from actual rows by 10x or more.
- Sequential scan on a table with >10K rows and a selective filter.
- Nested loop with large inner result set.
- Sort with `Sort Method: external merge Disk`.
