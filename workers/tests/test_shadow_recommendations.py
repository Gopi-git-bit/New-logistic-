"""Fake-only permission, ranking, fallback and operational isolation evidence."""

import ast
import asyncio
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path

import pytest
from test_m6_handlers import FakeM6Db

from zippy_workers import shadow_recommendations
from zippy_workers.capabilities import UnauthorizedCapability
from zippy_workers.handlers import assign_driver
from zippy_workers.shadow_recommendations import (
    FakeShadowAgent,
    SyntheticMatch,
    evaluate_shadow,
)

MATCHES = (SyntheticMatch(10, 9), SyntheticMatch(20, 8), SyntheticMatch(30, 7))
BASELINE = ("candidate-0", "candidate-1", "candidate-2")


def evaluate(agent, matches=MATCHES, **permissions):
    return asyncio.run(
        evaluate_shadow(
            matches,
            agent,
            agent_name=permissions.get("agent_name", "order_management"),
            action=permissions.get("action", "recommend_drivers"),
            tool=permissions.get("tool", "recommend_drivers"),
            timeout_seconds=0.01,
        )
    )


def test_exact_comparison_keeps_backend_order_not_feature_sort():
    matches = (SyntheticMatch(30, 7), SyntheticMatch(10, 9), SyntheticMatch(20, 8))
    report = evaluate(
        FakeShadowAgent('{"candidate_ids": ["candidate-2", "candidate-0", "candidate-1"]}'),
        matches,
    )
    assert report.baseline_ids == BASELINE
    assert report.advisory.source == "agent"
    assert not report.top_choice_agrees
    assert report.total_rank_displacement == 4
    assert tuple(asdict(item) for item in report.differences) == (
        {"candidate_id": "candidate-0", "baseline_rank": 1, "advisory_rank": 2},
        {"candidate_id": "candidate-1", "baseline_rank": 2, "advisory_rank": 3},
        {"candidate_id": "candidate-2", "baseline_rank": 3, "advisory_rank": 1},
    )
    with pytest.raises(FrozenInstanceError):
        report.total_rank_displacement = 0
    with pytest.raises(FrozenInstanceError):
        matches[0].score = 100


def test_agreement_and_empty_shortlist_shapes():
    report = evaluate(FakeShadowAgent(json.dumps({"candidate_ids": BASELINE})))
    assert report.top_choice_agrees
    assert report.differences == ()
    assert report.total_rank_displacement == 0
    empty = evaluate(FakeShadowAgent(outcome="failure"), ())
    assert empty.baseline_ids == ()
    assert empty.advisory.reason_code == "NO_CANDIDATES"
    assert empty.top_choice_agrees is None
    assert empty.total_rank_displacement == 0


@pytest.mark.parametrize(
    "permissions",
    [
        {"agent_name": name}
        for name in (
            "unknown",
            "customer_service",
            "transportation",
            "resource_management",
            "payment_settlement",
            "platform_administration",
            "communication",
            "document_processing",
        )
    ]
    + [
        {"action": action}
        for action in (
            "assign_driver",
            "generate_quote",
            "transition_order",
            "capture_payment",
            "approve_refund",
            "release_settlement",
            "approve_decision",
            "",
        )
    ]
    + [
        {"tool": tool}
        for tool in (
            "assign_driver",
            "razorpay",
            "stripe",
            "mapbox",
            "odoo",
            "paperclip",
            "hermes",
            "zoho",
            "vercel",
            "",
        )
    ],
)
def test_permissions_deny_before_any_agent_execution(permissions, monkeypatch):
    async def forbidden_call(*args, **kwargs):
        pytest.fail("denied request reached recommendation execution")

    monkeypatch.setattr(shadow_recommendations, "recommend_drivers", forbidden_call)
    with pytest.raises(UnauthorizedCapability, match="agent/action/tool denied"):
        evaluate(FakeShadowAgent(), **permissions)


def test_existing_read_capability_is_required_even_for_allowlisted_tuple(monkeypatch):
    monkeypatch.setattr(shadow_recommendations, "has_capability", lambda *args: False)
    with pytest.raises(UnauthorizedCapability):
        evaluate(FakeShadowAgent())


@pytest.mark.parametrize(
    "agent,reason",
    [
        (None, "AGENT_UNAVAILABLE"),
        (FakeShadowAgent(outcome="timeout"), "AGENT_TIMEOUT"),
        (FakeShadowAgent(outcome="unavailable"), "AGENT_UNAVAILABLE"),
        (FakeShadowAgent(outcome="failure"), "AGENT_FAILURE"),
        (FakeShadowAgent("not-json"), "MALFORMED_OUTPUT"),
        (FakeShadowAgent('{"candidate_ids": ["candidate-0"]}'), "MALFORMED_OUTPUT"),
        (
            FakeShadowAgent('{"candidate_ids": ["candidate-0", "candidate-0", "candidate-2"]}'),
            "MALFORMED_OUTPUT",
        ),
        (
            FakeShadowAgent('{"candidate_ids": ["candidate-0", "candidate-1", "outsider"]}'),
            "MALFORMED_OUTPUT",
        ),
    ],
)
def test_failures_preserve_exact_baseline_and_operational_state(agent, reason):
    state = {
        "assignment": {"driver": "synthetic-driver-0"},
        "prices": {"quote": 100},
        "orders": {"status": "inventory_confirmed"},
        "payments": {"captured": False},
        "refunds": {"manual_approval": "pending"},
        "settlements": {"pod_required": True, "approval": "pending"},
        "governance": {"decision_lock": True, "grant": None},
    }
    before = deepcopy(state)
    report = evaluate(agent)
    assert report.advisory.source == "deterministic"
    assert report.advisory.reason_code == reason
    assert report.advisory.candidate_ids == report.baseline_ids == BASELINE
    assert report.top_choice_agrees
    assert report.total_rank_displacement == 0
    assert state == before


@pytest.mark.parametrize(
    "domain",
    ["assignment", "prices", "orders", "payments", "refunds", "settlements", "governance"],
)
def test_mutation_bearing_output_is_rejected(domain):
    agent = FakeShadowAgent(json.dumps({"candidate_ids": BASELINE, domain: {"write": True}}))
    report = evaluate(agent)
    assert report.advisory.reason_code == "MALFORMED_OUTPUT"
    assert report.advisory.candidate_ids == BASELINE


def test_fake_only_boundary_rejects_custom_adapters_and_operational_inputs():
    class CustomAgent(FakeShadowAgent):
        async def rank(self, request):
            pytest.fail("custom adapter must not run")

    with pytest.raises(ValueError, match="built-in fake"):
        evaluate(CustomAgent())
    with pytest.raises(ValueError, match="SyntheticMatch"):
        evaluate(None, ({"user_id": "real-driver"},))
    with pytest.raises(ValueError, match="SyntheticMatch"):
        evaluate(None, list(MATCHES))


@pytest.mark.parametrize(
    "value", [True, float("nan"), float("inf"), 10**1000, "identity", object()]
)
def test_synthetic_features_reject_non_numeric_or_nonfinite_data(value):
    with pytest.raises(ValueError, match="finite numbers"):
        SyntheticMatch(score=value)


def test_shadow_disagreement_cannot_change_authoritative_assignment():
    db = FakeM6Db()
    db.orders["order-1"] = {"pickup_location": "SRID=4326;POINT(72.835 18.939)"}
    db.driver_matches = [
        {"user_id": "synthetic-driver-0", "distance_m": 10, "score": 9},
        {"user_id": "synthetic-driver-1", "distance_m": 20, "score": 8},
    ]
    before = deepcopy(vars(db))
    report = evaluate(
        FakeShadowAgent('{"candidate_ids": ["candidate-1", "candidate-0"]}'),
        MATCHES[:2],
    )
    assert not report.top_choice_agrees
    assert vars(db) == before
    assert assign_driver({"order_id": "order-1"}, db).ok
    assert db.assignments == [("order-1", "synthetic-driver-0", "driver")]


def test_harness_has_no_operational_ports_or_active_importers():
    root = Path(__file__).resolve().parents[2]
    source = root / "workers/src/zippy_workers/shadow_recommendations.py"
    tree = ast.parse(source.read_text())
    imports = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports == {
        "__future__",
        "asyncio",
        "json",
        "math",
        "dataclasses",
        "typing",
        "capabilities",
        "recommendations",
    }
    for folder in (root / "api", root / "workers/src/zippy_workers"):
        for path in folder.rglob("*.py"):
            if (
                path == source
                or path == source.with_name("recommendation_reviews.py")
                or "tests" in path.parts
                or "tests_m4" in path.parts
                or "tests_m5" in path.parts
            ):
                continue
            assert "shadow_recommendations" not in path.read_text(), path


def test_fake_configuration_and_deadline_errors_are_explicit():
    with pytest.raises(ValueError, match="unknown fake outcome"):
        FakeShadowAgent(outcome="live")
    with pytest.raises(ValueError, match="must be a string"):
        FakeShadowAgent(response_json={})
    with pytest.raises(ValueError, match="finite and positive"):
        asyncio.run(
            evaluate_shadow(
                MATCHES,
                None,
                agent_name="order_management",
                action="recommend_drivers",
                tool="recommend_drivers",
                timeout_seconds=0,
            )
        )


def test_timeout_is_bounded_and_cancelled_without_network_or_mutation_ports(monkeypatch):
    import socket

    async def scenario():
        def forbidden_network(*args, **kwargs):
            pytest.fail("synthetic harness attempted network I/O")

        monkeypatch.setattr(socket, "socket", forbidden_network)
        loop = asyncio.get_running_loop()
        started = loop.time()
        report = await asyncio.wait_for(
            evaluate_shadow(
                MATCHES,
                FakeShadowAgent(outcome="timeout"),
                agent_name="order_management",
                action="recommend_drivers",
                tool="recommend_drivers",
                timeout_seconds=0.01,
            ),
            timeout=0.2,
        )
        assert loop.time() - started < 0.2
        assert report.advisory.reason_code == "AGENT_TIMEOUT"
        assert report.advisory.candidate_ids == BASELINE
        await asyncio.sleep(0)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())
