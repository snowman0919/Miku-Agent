from tools.generate_duplex_bundle import SCENARIOS, build


def test_duplex_generator_produces_distinct_varied_timestamp_sequences():
    rows = build("00000000-0000-4000-8000-000000000020", 240, "a" * 64)
    bodies = {str(row["events"]) for row in rows}
    assert len(bodies) == len(rows)
    assert {row["scenario"] for row in rows} == set(SCENARIOS)
    assert {len(row["events"]) for row in rows} >= {4, 5, 6}
    assert any(row["provenance"]["overlap_ms"] > 0 for row in rows)
    assert any(row["provenance"]["silence_ms"] >= 2500 for row in rows)
