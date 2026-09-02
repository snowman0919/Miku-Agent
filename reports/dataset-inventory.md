# Dataset Inventory

2026-09-03 local pilot registry 기준이다.

- Sources 20: quarantine 14, frozen holdout 6.
- Objects 10: 320,440 bytes on disk; integrity failures 0.
- Audio samples 100, decoded object metrics 10.
- Text samples 256, persona samples 1,000, agentic trajectories 500, duplex timelines 500.
- Reviews 1, remote jobs 1 (`waiting_for_lease`).
- Entire data root footprint after three retained pilot snapshots: 약 3.8 MiB.

실제 media와 SQLite/Parquet는 Git 밖에 있으며 이 report는 aggregate와 digest만 포함한다.
