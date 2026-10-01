# COMEDK Compass — Backend Test Database Isolation

## Overview

To prevent accidental modification or corruption of the active development database (`comedk_compass`), all backend automated tests executed via `pytest` run against an **isolated test database** (`comedk_compass_test`).

`conftest.py` strictly enforces this requirement:
1. `TEST_DATABASE_URL` must be configured (via `.env` or system environment variables).
2. If `TEST_DATABASE_URL` is missing, `pytest` aborts execution immediately with exit code 1.
3. If `TEST_DATABASE_URL` is set to the same database as `DATABASE_URL` (development), `pytest` aborts execution immediately to protect development data.
4. Database sessions provided by the `db` fixture or used by the FastAPI `client` fixture are rebound to `TEST_DATABASE_URL`.
5. The `db` fixture is function-scoped and performs automatic rollback on teardown.

---

## Initial Setup of the Test Database

Because prediction validation, historical analytics, and regression tests rely on realistic baseline records (the 12,000 official COMEDK cutoffs), create the test database by cloning the schema and data from the development database:

### Using PostgreSQL `createdb`:
```bash
# Terminate any active connections to template if necessary, then clone:
createdb -U postgres -h 127.0.0.1 -T comedk_compass comedk_compass_test
```

### Or using SQL in `psql`:
```sql
CREATE DATABASE comedk_compass_test TEMPLATE comedk_compass;
```

---

## Environment Configuration

Configure `TEST_DATABASE_URL` in your `.env` file:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/comedk_compass
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/comedk_compass_test
```

---

## Running the Tests

To run the backend test suite:

```bash
.venv\Scripts\pytest.exe backend/tests -v
```

If you temporarily run without `TEST_DATABASE_URL`:
```bash
$ env -u TEST_DATABASE_URL pytest backend/tests
CONFIGURATION ERROR: TEST_DATABASE_URL is not set.
Pytest is prevented from running against the development DATABASE_URL to avoid accidental mutation.
```
