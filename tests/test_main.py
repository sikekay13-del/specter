import json

import main


class FailingModule:
    name = "test"

    def can_run(self, target_type):
        return True

    def run(self, target):
        raise RuntimeError("simulated failure")


def test_module_failure_is_reported_as_could_not_check(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "OUT_DIR", str(tmp_path))

    main.run_and_report([FailingModule()], "sample", "username")

    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert results["total_could_not_check"] == 1
    assert results["results"][0]["state"] == "COULD NOT CHECK"
    assert results["results"][0]["source"] == "test module"
