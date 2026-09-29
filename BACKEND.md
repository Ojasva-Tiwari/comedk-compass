# COMEDK Compass - Backend & Data Foundation (Stage 1)

Production-quality data ingestion, normalization, validation, and REST API foundation for COMEDK engineering counselling.

---

## Architecture Overview

```
official COMEDK website (comedk.org)
  │
  ├── 1. Discovery (OfficialSourceDiscovery)
  │     ├── /member-institutions
  │     ├── /be-colleges
  │     └── /counselling-document-2026 (cutoffs, seat matrices, fee structures)
  │
  ├── 2. Download & Archive (DocumentArchiver)
  │     ├── SHA-256 Content Hashing
  │     └── Directory: data/raw/comedk/{academic_year}/{folder}/
  │
  ├── 3. Parsing & Extraction (BaseParser, CutoffPDFParser, SeatAndFeeParser)
  │     ├── Text-extractability inspection (Fail closed on scanned/empty PDFs)
  │     ├── PyMuPDF (fitz) + pdfplumber
  │     └── OCRInterface pluggable abstraction
  │
  ├── 4. Normalization (Normalizer)
  │     ├── College codes (e.g. E001) & smart-casing acronyms (BMS, RV, MSRIT, PES)
  │     ├── Branch codes & standardized branch names
  │     └── Categories (GM, KKR, HKR) and Rounds (MOCK, R1, R2, R3, R4)
  │
  ├── 5. Validation & Anomaly Detection (DataValidator)
  │     ├── Positive rank checks
  │     ├── Opening rank <= Closing rank enforcement
  │     ├── College & branch referential integrity
  │     ├── Duplicate logical record suppression
  │     └── Outlier & anomaly reporting
  │
  └── 6. Persistence & Provenance (PostgreSQL: comedk_compass)
        ├── Full audit trail in `source_versions` and `validation_errors`
        ├── Published records: colleges, branches, cutoff_records, seat_records, fee_records
        └── REST APIs & Admin Data-Health Dashboard
```

---

## Prerequisites

- **Python**: 3.12+ (tested on Python 3.13)
- **PostgreSQL**: PostgreSQL 18 running on `localhost:5432`

---

## Setup & Configuration

1. **Environment Setup**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Ensure `.env` points to your PostgreSQL database:
   ```ini
   DATABASE_URL=postgresql+psycopg://postgres:<PASSWORD>@127.0.0.1:5432/comedk_compass
   APP_ENV=development
   RAW_DATA_DIR=data/raw/comedk
   HTTP_TIMEOUT=30.0
   PARSER_VERSION=1.0.0
   ```

2. **Database Migrations**:
   Run Alembic to apply the latest database schema:
   ```bash
   .\.venv\Scripts\alembic upgrade head
   ```

3. **Running Pytest Test Suite**:
   ```bash
   .\.venv\Scripts\pytest backend/tests/ -v
   ```

4. **Running Real Ingestion**:
   To execute live discovery and ingestion against official COMEDK sources:
   ```bash
   .\.venv\Scripts\python backend/run_ingestion.py
   ```

5. **Starting the FastAPI Server**:
   ```bash
   .\.venv\Scripts\uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

6. **Interactive Documentation & Admin UI**:
   - Swagger API Docs: `http://127.0.0.1:8000/docs`
   - ReDoc: `http://127.0.0.1:8000/redoc`
   - Internal Data Health Dashboard: `http://127.0.0.1:8000/data-health`

---

## REST Endpoints (`/api/v1`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service and database connectivity health check |
| `GET` | `/api/v1/data-health` | Comprehensive counts, ingestion status, and anomaly tallies |
| `GET` | `/api/v1/colleges` | Paginated colleges list with search and location filter |
| `GET` | `/api/v1/colleges/{id}` | Detailed college profile with official aliases |
| `GET` | `/api/v1/branches` | Paginated branches with code/name search |
| `GET` | `/api/v1/sources` | Official source catalog with SHA-256 provenance versions |
| `GET` | `/api/v1/cutoffs` | Published cutoff ranks filterable by college, branch, round, and quota |
| `GET` | `/api/v1/seat-records` | Seat capacity and vacancy metrics |
| `GET` | `/api/v1/fees` | Official tuition and total fee schedules |
