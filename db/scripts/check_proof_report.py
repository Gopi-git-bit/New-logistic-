"""Reject skipped, failed or incomplete disposable database proofs."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

# Minimum real integration cases observed in PR #12's 72 skipped tests.
# Existing unit/mock tests remain in the suites and cannot satisfy these counts.
REQUIRED = {
    "operations": {
        "test_postgres_integration": 2,
        "test_dispatch_integration": 31,
        "test_finance_integration": 23,
        "test_payment_intent_privileges": 4,
    },
    "governance": {"test_integration": 12},
}


def verify_report(path: Path, proof: str) -> tuple[int, int]:
    """Require successful, unique test cases and the real integration groups."""
    required = REQUIRED[proof]
    data = path.read_bytes()
    if len(data) > 4_194_304:
        raise ValueError("report too large")
    root = ET.fromstring(data)
    if root.tag not in {"testsuites", "testsuite"}:
        raise ValueError("invalid report root")
    if any(root.findall(f".//{tag}") for tag in ("skipped", "failure", "error")):
        raise ValueError("unsuccessful tests")
    cases = root.findall(".//testcase")
    identities = [(case.attrib["classname"], case.attrib["name"]) for case in cases]
    if not cases or len(set(identities)) != len(identities):
        raise ValueError("missing or duplicate tests")
    counts = Counter(classname.rsplit(".", 1)[-1] for classname, _ in identities)
    if any(counts[name] < count for name, count in required.items()):
        raise ValueError("required integration coverage missing")
    return len(cases), sum(counts[name] for name in required)


def main() -> int:
    try:
        if len(sys.argv) != 3:
            raise ValueError("invalid arguments")
        proof = sys.argv[2]
        total, integration = verify_report(Path(sys.argv[1]), proof)
    except (OSError, ValueError, KeyError, ET.ParseError):
        print("DATABASE_PROOF_REPORT_REJECTED")
        return 1
    print(
        f"database_proof_tests=PASS proof={proof} total={total} "
        f"integration={integration} skipped=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
