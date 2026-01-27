# Bolt's Journal

## 2024-05-23 - [Initial Setup]
**Learning:** Bolt journal initialized.
**Action:** Record critical performance learnings here.

## 2024-05-23 - [Missing Foreign Key Indexes]
**Learning:** SQLAlchemy `ForeignKey` columns in `services/api` do not automatically create indexes. This leads to missing indexes on critical relationship columns like `Project.client_id`, `ProjectDomain.project_id`, and `ApiKey.project_id`.
**Action:** Always verify `index=True` is explicitly set on `ForeignKey` columns that are frequently used for lookups or joins.
