# Migrating from a filesystem vault

If you already keep career data as:

```text
CAREER_VAULT_ROOT/
  current/career-truth.json
  applications/<id>/
    meta.json
    jd.txt
    generations/*.md
    generations/*.meta.json   # optional
```

Import into Sprucer (SQLite or Postgres):

```bash
sprucer import-vault /path/to/CAREER_VAULT_ROOT --database-url sqlite:///./data/sprucer.db
```

The importer:

1. Loads `current/career-truth.json` into the truth document
2. Creates application rows from each `applications/<id>/meta.json`
3. Stores JD text and generation markdown + approval metadata

It does **not** delete the source tree. Review the UI after import.

Sprucer does not recommend the filesystem layout for new installs.
