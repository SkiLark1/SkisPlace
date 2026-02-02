## 2024-05-22 - Missing Indexes on High Volume Tables
**Learning:** High-volume event tables (`UsageEvent`, `ErrorEvent`) were missing database indexes on critical filtering columns (`project_id`, `timestamp`), leading to potential full table scans.
**Action:** Always verify `index=True` is explicitly set on `ForeignKey` columns and timestamp columns in SQLAlchemy models for high-traffic tables.
