## 2026-01-28 - Missing Default Indexes on ForeignKeys
**Learning:** SQLAlchemy (unlike Django) does not automatically create indexes for `ForeignKey` columns. This can lead to silent performance killers on join operations or filtering by parent IDs.
**Action:** Always explicitly add `index=True` to `mapped_column(ForeignKey(...))` definitions unless there's a specific reason not to.
