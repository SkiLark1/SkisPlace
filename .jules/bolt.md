## 2026-01-23 - SQLAlchemy Foreign Keys and Indexes
**Learning:** SQLAlchemy `ForeignKey` columns in `services/api` models do not automatically create indexes. This led to a performance bottleneck in high-volume tables (`usage_events`, `error_events`).
**Action:** Always explicitly add `index=True` to `mapped_column` definitions for Foreign Keys and other frequently filtered columns.
