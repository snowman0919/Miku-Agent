# Dataset Inventory

2026-09-03 canonical registry와 `miku-data-d0.2.0-alpha8` snapshot 기준이다.

| Class | Sources | Audio | Text | Persona | Agentic | Duplex | Training state |
|---|---:|---:|---:|---:|---:|---:|---|
| infrastructure fixture | 15 | 100 | 256 | 1,000 | 500 | 500 | quarantine |
| candidate corpus | 1 | 0 | 20,000 | 0 | 0 | 0 | quarantine |
| quarantine real corpus | 0 | 0 | 0 | 0 | 0 | 0 | n/a |
| accepted corpus | 2 | 0 | 0 | 0 | 1 | 2,000 | accepted 2,001 |
| evaluation corpus | 6 | 1,000 | 3,500 | 0 | 0 | 500 | frozen holdout |

- Sample records 29,357, sources 24, objects 1,164, object bytes 309,181,451.
- Audio rows 1,100, unique sample/object identity 1,010/1,010, referenced duration 5,891,723 ms.
- Unique physical interval duration 5,801,723 ms; effective accepted speech 0 ms.
- Candidate script는 exact unique 20,000이지만 0.8 Jaccard character/token 군집은
  5,987/10,616개, E5 cosine 0.98/0.99 semantic 군집은 1,536/7,715개다.
- Accepted Duplex 2,000행은 event sequence가 모두 다르지만 normalized text 1,955개,
  character/token lexical 군집 1,877/1,939개, E5 cosine 0.98/0.99 semantic 군집 582/1,453개다.
- Reviews 2,465, evidence-backed reviews 2,003, human corpus reviews 0, worker jobs 463, successful result imports 461.
- Canonical root의 raw media, SQLite와 Parquet는 Git 밖에 있다.
