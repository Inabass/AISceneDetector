# Database Migrations

Alembic manages SQLite schema changes. Do not create application tables with
`Base.metadata.create_all()` in runtime code.

Run migrations with:

```bat
python -m app.db.migrate
```
