## 2026-02-04 - Missing Foreign Key Indexes
**Learning:** SQLAlchemy `ForeignKey` columns do not automatically create database indexes. In `UsageEvent` and `ErrorEvent` tables, `project_id` and `module_id` were unindexed, likely causing full table scans during filtering.
**Action:** Always verify if `index=True` or `unique=True` is needed when defining `ForeignKey` columns in SQLAlchemy models, especially for high-volume tables used in analytics.
