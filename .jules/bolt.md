## 2026-01-23 - Missing Foreign Key Indexes
**Learning:** SQLAlchemy's `ForeignKey` does not automatically generate database indexes in Postgres. This led to potential N+1 or slow filtering issues in `UsageEvent` and `Project` lookups.
**Action:** Always explicitly add `index=True` to `mapped_column(ForeignKey(...))` if the column is used for filtering or joining.
