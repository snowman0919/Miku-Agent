# Dataset Inventory

2026-09-03 canonical registry와 `miku-data-d0.2.0-alpha10` snapshot 기준이다.

| Class | Sources | Audio | Text | Persona | Agentic | Duplex | Training state |
|---|---:|---:|---:|---:|---:|---:|---|
| infrastructure fixture | 15 | 100 | 256 | 1,000 | 500 | 500 | quarantine |
| candidate corpus | 1 | 0 | 20,000 | 0 | 0 | 0 | quarantine |
| quarantine real corpus | 0 | 0 | 0 | 0 | 0 | 0 | n/a |
| accepted corpus | 3 | 0 | 78,112 | 0 | 3 | 2,000 | accepted 80,115 |
| evaluation corpus | 6 | 1,000 | 3,500 | 0 | 0 | 500 | frozen holdout |

- Sample records 107,471, sources 25, objects 1,179, object bytes 1,879,996,948.
- Audio rows 1,100, unique sample/object identity 1,010/1,010, referenced duration 5,891,723 ms.
- Unique physical interval duration 5,801,723 ms; effective accepted speech 0 ms.
- Accepted Korean foundation text는 78,112 documents, 129,341,916 tokens다. E5 cosine
  0.98/0.99 semantic effective unique는 78,082/78,110이며 exact와 Jaccard 0.8
  character/token effective unique는 모두 78,112다.
- Candidate script는 exact unique 20,000이지만 0.8 Jaccard character/token 군집은
  5,987/10,616개, E5 cosine 0.98/0.99 semantic 군집은 1,536/7,715개다.
- Accepted Duplex 2,000행은 event sequence가 모두 다르지만 normalized text 1,955개,
  character/token lexical 군집 1,877/1,939개, E5 cosine 0.98/0.99 semantic 군집 582/1,453개다.
- Primary accepted effective unique는 Korean text 78,082 + Agentic receipt 3 + Duplex semantic 582 = 78,667이다.
- Reviews 80,580, evidence-backed reviews 80,118, human corpus reviews 0, worker jobs 463,
  successful result imports 461이다.
- Canonical root의 raw media, SQLite, Parquet와 training export는 Git 밖에 있다.
