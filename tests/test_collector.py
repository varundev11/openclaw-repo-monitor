import os
from collector import MonitorCollector

def test_missing_token(monkeypatch):
    monkeypatch.delenv('GIST_TOKEN', raising=False)
    try:
        MonitorCollector()
        assert False, "should have raised"
    except RuntimeError:
        assert True
