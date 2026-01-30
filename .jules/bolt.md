## 2024-05-22 - Missing Database Indexes on High Volume Tables
**Learning:** `ForeignKey` columns in SQLAlchemy do not automatically create database indexes. For high-volume tables like `usage_events` and `error_events`, missing indexes on foreign keys (like `project_id`) and filter columns (like `timestamp`) can cause severe performance degradation (full table scans).
**Action:** Always explicitly add `index=True` to `ForeignKey` columns and common filter columns in SQLAlchemy models, especially for event/log tables.
