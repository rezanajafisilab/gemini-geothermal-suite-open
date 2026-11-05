"""Verify the preserved cooling source pack without changing it (M0)."""

import csv
import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path


def verify(root):
    """Return independent source hashes, calendar checks and demand totals."""
    paths = [root / "hackathon/docs/cooling/START_HERE.md"] + sorted((root / "hackathon/data/raw").rglob("*"))
    hashes = {
        str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
        if p.is_file()
    }
    register = (root / "hackathon/docs/cooling/SOURCES_AND_ASSUMPTIONS.md").read_text(
        encoding="utf-8"
    )
    for path, digest in re.findall(
        r"Root path: `([^`]+)`.*?SHA-256: `([0-9a-f]{64})`", register, re.S
    ):
        assert hashes[path] == digest, f"Original source changed: {path}"
    previous = root / "hackathon/docs/cooling/M0_EVIDENCE.json"
    if previous.exists():
        for path, digest in json.loads(previous.read_text())["hashes"].items():
            assert hashes[path] == digest, f"Pack source changed since M0: {path}"
    demands = {}
    for mode, field in [("Heating", "heating_demand_MWth"), ("Cooling", "cooling_demand_MWcool")]:
        path = root / f"hackathon/data/raw/challenge/GEMINI_{mode}_Demand_Daily_2027.csv"
        with path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert [r["date"] for r in rows] == [
            str(date(2027, 1, 1) + timedelta(days=i)) for i in range(365)
        ]
        demands[field] = {r["date"]: float(r[field]) for r in rows}
    totals = {k: sum(v.values()) * 24 for k, v in demands.items()}
    assert abs(totals["heating_demand_MWth"] - 111667.680) < 1e-6
    assert abs(totals["cooling_demand_MWcool"] - 23742.528) < 1e-6
    for name, count in [("Hourly", 8760), ("Daily", 365)]:
        path = (
            root
            / "hackathon/data/raw/weather/knmi_debilt_2025"
            / f"GEMINI_Weather_{name}_2027_KNMI_DeBilt_2025.csv"
        )
        with path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == count
        for r in rows:
            for field in demands:
                assert float(r[field]) == demands[field][r["date"]]
    return {"hashes": hashes, "demand_mwh": totals, "weather_rows": [8760, 365]}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    result = verify(root)
    target = root / "hackathon/docs/cooling/M0_EVIDENCE.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(result["demand_mwh"], result["weather_rows"])
