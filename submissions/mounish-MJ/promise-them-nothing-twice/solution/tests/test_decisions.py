def test_decisions_document_priya_marcus_conflict():
    import os
    path = "DECISIONS.md" if os.path.exists("DECISIONS.md") else "../DECISIONS.md"
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    assert "Priya Nair requires hard enforcement" in content
    assert "Marcus Webb requires that Northwind never see a 429" in content
    assert "no customer exceeds its configured effective quota" in content
    assert "hidden Northwind bypass" in content
    assert "explicit, configurable, and auditable" in content
