"""Run the trust benchmark.

    python -m bench           print the scores and refresh bench/results.json
    python -m bench --check   fail if results.json is out of date
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from bench import crosscheck, factcheck_bench, sql_guard_bench

RESULTS = Path(__file__).with_name("results.json")


def run_all() -> dict:
    """Run every suite. The result is deterministic apart from ``generated``."""
    return {
        "generated": datetime.now(UTC).strftime("%Y-%m-%d"),
        "factcheck": factcheck_bench.run(),
        "sql_guard": sql_guard_bench.run(),
        "crosscheck": crosscheck.run(),
    }


def load() -> dict:
    """The published results."""
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def same_scores(a: dict, b: dict) -> bool:
    """True if two result sets match, ignoring the date they were made."""
    strip = lambda r: {k: v for k, v in r.items() if k != "generated"}  # noqa: E731
    return strip(a) == strip(b)


def summary(r: dict) -> str:
    """A short plain-text report."""
    fc, sg, cc = r["factcheck"], r["sql_guard"], r["crosscheck"]
    lines = [
        "Veridash trust benchmark",
        f"  Fact-check: caught {fc['caught']:,} of {fc['planted_errors']:,} planted errors ({fc['catch_pct']}%), "
        f"{fc['false_alarms']} false alarms on {fc['correct_sentences']:,} correct sentences",
    ]
    lines += [f"    {row['title']:<26} {row['flagged']:>4}/{row['cases']:<4} caught" for row in fc["corrupt"]]
    lines += [
        f"  SQL guard: blocked {sg['guard_blocked']} of {sg['attacks']} harmful queries; sandbox alone blocked "
        f"{sg['sandbox_blocked']} of {sg['sandbox_attacks']}; {sg['harmless_ran']} of {sg['harmless']} harmless ran",
        f"  Cross-check: {cc['matched']} of {cc['checked']} numbers match an independent pandas recomputation",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    results = run_all()
    print(summary(results))
    if "--check" in argv:
        if not RESULTS.exists() or not same_scores(load(), results):
            print("bench/results.json is out of date: run python -m bench", file=sys.stderr)
            return 1
        return 0
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {RESULTS.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
