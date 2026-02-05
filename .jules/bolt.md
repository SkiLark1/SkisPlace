## 2026-02-05 - SQLAlchemy Foreign Keys and Indexes
**Learning:** SQLAlchemy's `ForeignKey` does not automatically create an index on the column. This leads to missing indexes on critical relationship columns (e.g., `project_id`), causing full table scans during joins and filters.
**Action:** Always explicitly add `index=True` to `mapped_column(ForeignKey(...))` unless there is a specific reason not to.
