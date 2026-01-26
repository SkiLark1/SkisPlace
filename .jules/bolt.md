## 2024-05-22 - Database Interaction Anti-Patterns
**Learning:** Found critical performance issues: 1) `echo=True` enabled in `session.py` causing massive logging overhead. 2) Duplicate `commit/refresh` blocks in endpoints causing 2x database roundtrips.
**Action:** Inspect `db/session.py` immediately for debug flags and check for redundant DB operations in endpoints.
