## 2024-01-26 - Manual Migrations Risk
**Learning:** The inability to use `alembic revision --autogenerate` (due to missing DB connectivity) leads to manual migration creation. This manual process is error-prone, resulting in missing indexes on high-volume tables like `usage_events` and `error_events` even when the models might imply them (or developers forget to add `index=True` in models too).
**Action:** Always manually verify that new models or foreign keys have corresponding `index=True` and that the manual migration script explicitly includes `op.create_index`.
