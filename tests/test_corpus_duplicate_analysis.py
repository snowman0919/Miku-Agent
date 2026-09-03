from tools.analyze_corpus_duplicates import exact_clusters, lexical_clusters, normalize


def test_duplicate_analysis_finds_normalized_and_lexical_clusters():
    texts = ["빌드 결과를 다시 확인해 줘", "  빌드 결과를 다시 확인해 줘  ",
             "빌드 결과를 다시 확인해 줘!", "오늘 날씨가 맑아"]
    assert normalize(texts[0]) == normalize(texts[1])
    assert exact_clusters(texts)["effective_unique_rows"] == 3
    result = lexical_clusters(texts, "character_5gram", 600_000, 64, 16)
    assert result["effective_unique_rows"] == 2
    assert result["largest_cluster_rows"] == 3
