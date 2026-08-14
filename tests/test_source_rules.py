from pathlib import Path


def test_no_try_catch_around_imports():
    # Project convention: dependencies fail clearly rather than being hidden at import time.
    assert "try:\n    import" not in "\n".join(
        p.read_text() for p in Path("src").glob("*.py")
    )
