## 2026-01-24 - Missing Indexes on High Volume Tables
**Learning:** SQLAlchemy `ForeignKey` does not automatically create an index on the referencing column. This is a common pitfall. High-volume tables like `usage_events` and `error_events` were missing indexes on `project_id` and `timestamp`, likely causing slow queries as data grows.
**Action:** Always explicitly add `index=True` to `ForeignKey` columns or any column used for filtering in `WHERE` clauses, especially for event/log tables.
