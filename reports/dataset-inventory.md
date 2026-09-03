# Dataset Inventory

2026-09-03 canonical registry와 `miku-data-d0.2.0-alpha6` snapshot 기준이다.

| Class | Sources | Audio | Text | Persona | Agentic | Duplex | Training state |
|---|---:|---:|---:|---:|---:|---:|---|
| infrastructure fixture | 15 | 100 | 256 | 1,000 | 500 | 500 | quarantine |
| candidate corpus | 1 | 0 | 20,000 | 0 | 0 | 0 | quarantine |
| quarantine real corpus | 0 | 0 | 0 | 0 | 0 | 0 | n/a |
| accepted corpus | 1 | 0 | 0 | 0 | 1 | 0 | accepted 1 |
| evaluation corpus | 6 | 1,000 | 3,500 | 0 | 0 | 500 | frozen holdout |

- Sample records 27,357, sources 23, objects 1,162, object bytes 306,436,585.
- Audio rows 1,100, unique sample/object identity 1,010/1,010, referenced duration 5,891,723 ms.
- Unique physical interval duration 5,801,723 ms; effective accepted speech 0 ms.
- Candidate script exact unique 20,000이지만 semantic effective unique는 아직 측정하지 않았다.
- Reviews 463, evidence-backed reviews 2, human corpus reviews 0, worker jobs 462, successful result imports 460.
- Canonical root의 raw media, SQLite와 Parquet는 Git 밖에 있다.
