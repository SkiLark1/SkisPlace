
## 2024-05-24 - Missing Indexes on Foreign Keys
**Learning:** SQLAlchemy's `ForeignKey` does not imply `index=True`. The codebase consistently omitted indexes on FKs, leading to potential N+1 or slow join performance on parent-child lookups.
**Action:** When adding new relationships, always explicitly add `index=True` to the FK column unless there is a specific reason not to.
