"""Synthetic review lifecycle, retry, identity and operational isolation evidence."""

import ast
import asyncio
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_m6_handlers import FakeM6Db

from zippy_workers.handlers import assign_driver
from zippy_workers.recommendation_reviews import (
    ExpiredReview,
    FakeReviewer,
    FakeReviewStore,
    ReviewConflict,
    StaleReview,
    SyntheticCandidateSnapshot,
    UnauthorizedReviewer,
)
from zippy_workers.shadow_recommendations import FakeShadowAgent, SyntheticMatch

NOW = datetime(2026, 10, 9, tzinfo=UTC)
EXPIRY = NOW + timedelta(minutes=5)
MATCHES = (SyntheticMatch(10, 9), SyntheticMatch(20, 8))
SNAPSHOT = SyntheticCandidateSnapshot("synthetic-shortlist-v1", MATCHES)
AGENT = FakeShadowAgent('{"candidate_ids": ["candidate-1", "candidate-0"]}')


def create(store, **changes):
    inputs = {
        "review_id": "synthetic-review-1",
        "snapshot": SNAPSHOT,
        "agent": AGENT,
        "now": NOW,
        "expires_at": EXPIRY,
        "timeout_seconds": 0.01,
    }
    inputs.update(changes)
    return asyncio.run(store.create(**inputs))


def submit(store, **changes):
    inputs = {
        "review_id": "synthetic-review-1",
        "current_snapshot": SNAPSHOT,
        "reviewer": FakeReviewer.HUMAN_A,
        "decision": "accepted",
        "advisory_preference": "candidate-1",
        "idempotency_key": "synthetic-submission-1",
        "now": NOW + timedelta(seconds=1),
    }
    inputs.update(changes)
    return store.review(**inputs)


@pytest.fixture
def store():
    result = FakeReviewStore()
    create(result)
    return result


@pytest.mark.parametrize("reviewer", [FakeReviewer.HUMAN_A, FakeReviewer.HUMAN_B])
def test_pending_to_accepted_is_an_immutable_advisory_preference(store, reviewer):
    pending = store.get("synthetic-review-1", now=NOW)
    assert pending.status == "pending"
    assert pending.snapshot == SNAPSHOT
    assert pending.recommendation.candidate_ids == ("candidate-1", "candidate-0")
    assert pending.recommendation.source == "agent"
    assert pending.advisory_preference is None
    accepted = submit(store, reviewer=reviewer)
    assert accepted.status == "accepted"
    assert accepted.reviewer is reviewer
    assert accepted.advisory_preference == "candidate-1"
    assert accepted.updated_at == NOW + timedelta(seconds=1)
    assert pending.status == "pending"
    with pytest.raises(FrozenInstanceError):
        accepted.status = "rejected"
    with pytest.raises(FrozenInstanceError):
        accepted.snapshot.matches = ()


def test_rejected_records_identity_without_preference(store):
    rejected = submit(store, decision="rejected", advisory_preference=None)
    assert rejected.status == "rejected"
    assert rejected.reviewer is FakeReviewer.HUMAN_A
    assert rejected.advisory_preference is None


@pytest.mark.parametrize("offset", [timedelta(0), timedelta(seconds=1)])
def test_exact_expiry_is_terminal_and_idempotent(store, offset):
    assert store.get("synthetic-review-1", now=EXPIRY - timedelta(microseconds=1)).status == (
        "pending"
    )
    expired = store.get("synthetic-review-1", now=EXPIRY + offset)
    assert expired.status == "expired"
    assert expired.updated_at == EXPIRY
    assert expired.reviewer is None
    assert expired.advisory_preference is None
    assert store.get("synthetic-review-1", now=EXPIRY + timedelta(days=1)) is expired
    with pytest.raises(ExpiredReview, match="expired"):
        submit(store, now=EXPIRY + offset)


def test_submission_at_deadline_expires_without_read_first(store):
    with pytest.raises(ExpiredReview):
        submit(store, now=EXPIRY)
    assert store.get("synthetic-review-1", now=EXPIRY).status == "expired"


def test_acceptance_one_microsecond_before_expiry_remains_accepted(store):
    result = submit(store, now=EXPIRY - timedelta(microseconds=1))
    assert result.status == "accepted"
    assert store.get("synthetic-review-1", now=EXPIRY + timedelta(days=1)) is result


@pytest.mark.parametrize(
    "snapshot",
    [
        SyntheticCandidateSnapshot("synthetic-shortlist-v2", MATCHES),
        SyntheticCandidateSnapshot("synthetic-shortlist-v1", tuple(reversed(MATCHES))),
        SyntheticCandidateSnapshot("synthetic-shortlist-v1", (SyntheticMatch(11, 9), MATCHES[1])),
        SyntheticCandidateSnapshot("synthetic-shortlist-v1", (SyntheticMatch(10, 10), MATCHES[1])),
        SyntheticCandidateSnapshot("synthetic-shortlist-v1", MATCHES[:1]),
        SyntheticCandidateSnapshot("synthetic-shortlist-v1", ()),
        {"snapshot_id": "synthetic-shortlist-v1", "matches": MATCHES},
        None,
    ],
)
def test_stale_or_mismatched_snapshot_is_rejected_before_write(store, snapshot):
    pending = store.get("synthetic-review-1", now=NOW)
    with pytest.raises(StaleReview, match="exact current candidate snapshot"):
        submit(store, current_snapshot=snapshot)
    assert store.get("synthetic-review-1", now=NOW) is pending


def test_equivalent_exact_snapshot_fixture_can_be_reviewed(store):
    snapshot = SyntheticCandidateSnapshot("synthetic-shortlist-v1", MATCHES)
    assert submit(store, current_snapshot=snapshot).status == "accepted"


@pytest.mark.parametrize(
    "reviewer",
    [
        FakeReviewer.AGENT,
        FakeReviewer.OUTSIDER,
        "synthetic-human-a",
        "order_management",
        "platform_administration",
        None,
    ],
)
def test_fake_identity_denial_precedes_mutation_and_duplicate_replay(store, reviewer):
    pending = store.get("synthetic-review-1", now=NOW)
    with pytest.raises(UnauthorizedReviewer, match="explicit fake human"):
        submit(store, reviewer=reviewer)
    assert store.get("synthetic-review-1", now=NOW) is pending
    accepted = submit(store)
    with pytest.raises(UnauthorizedReviewer):
        submit(store, reviewer=reviewer)
    assert store.get("synthetic-review-1", now=accepted.updated_at) is accepted


@pytest.mark.parametrize("decision,preference", [("accepted", "candidate-1"), ("rejected", None)])
def test_identical_submission_retry_returns_original_even_after_expiry(store, decision, preference):
    result = submit(store, decision=decision, advisory_preference=preference)
    replay = submit(
        store, decision=decision, advisory_preference=preference, now=EXPIRY + timedelta(days=1)
    )
    assert replay is result
    assert replay.updated_at == NOW + timedelta(seconds=1)


@pytest.mark.parametrize(
    "changes",
    [
        {"decision": "rejected", "advisory_preference": None},
        {"advisory_preference": "candidate-0"},
        {"reviewer": FakeReviewer.HUMAN_B},
    ],
)
def test_duplicate_key_conflicts_are_explicit_without_overwriting(store, changes):
    result = submit(store)
    with pytest.raises(ReviewConflict, match="different review inputs"):
        submit(store, **changes)
    assert store.get("synthetic-review-1", now=result.updated_at) is result


def test_submission_key_is_bound_to_review_id_across_store(store):
    submit(store)
    create(store, review_id="synthetic-review-2")
    with pytest.raises(ReviewConflict):
        submit(store, review_id="synthetic-review-2")
    assert store.get("synthetic-review-2", now=NOW).status == "pending"


@pytest.mark.parametrize("decision,preference", [("accepted", "candidate-1"), ("rejected", None)])
def test_terminal_record_cannot_be_changed_with_new_submission_key(store, decision, preference):
    result = submit(store, decision=decision, advisory_preference=preference)
    with pytest.raises(ReviewConflict, match="terminal review"):
        submit(store, idempotency_key="synthetic-submission-2")
    assert store.get("synthetic-review-1", now=result.updated_at) is result


def test_stale_duplicate_is_not_success_shaped(store):
    submit(store)
    with pytest.raises(StaleReview):
        submit(store, current_snapshot=replace(SNAPSHOT, snapshot_id="synthetic-shortlist-v2"))


def test_creation_replay_returns_original_without_resetting_review(store):
    pending = create(store)
    accepted = submit(store)
    assert create(store) is pending
    assert store.get("synthetic-review-1", now=accepted.updated_at) is accepted


@pytest.mark.parametrize(
    "changes",
    [
        {"snapshot": replace(SNAPSHOT, snapshot_id="synthetic-shortlist-v2")},
        {"agent": None},
        {"now": NOW + timedelta(seconds=1)},
        {"expires_at": EXPIRY + timedelta(seconds=1)},
        {"timeout_seconds": 0.02},
    ],
)
def test_creation_id_conflict_does_not_overwrite(store, changes):
    pending = store.get("synthetic-review-1", now=NOW)
    with pytest.raises(ReviewConflict, match="different creation inputs"):
        create(store, **changes)
    assert store.get("synthetic-review-1", now=NOW) is pending


def test_concurrent_creations_are_idempotent_and_conflicts_do_not_overwrite():
    async def scenario():
        result = FakeReviewStore()

        async def run(expires_at=EXPIRY):
            return await result.create(
                "synthetic-review-1",
                SNAPSHOT,
                AGENT,
                now=NOW,
                expires_at=expires_at,
                timeout_seconds=0.01,
            )

        first, second = await asyncio.gather(run(), run())
        assert first is second
        with pytest.raises(ReviewConflict):
            await run(EXPIRY + timedelta(seconds=1))
        assert result.get("synthetic-review-1", now=NOW) is first

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "changes",
    [
        {"decision": "assign_driver"},
        {"decision": "pending"},
        {"decision": "expired"},
        {"advisory_preference": "outsider"},
        {"advisory_preference": {"payments": {"write": True}}},
        {"advisory_preference": None},
        {"decision": "rejected", "advisory_preference": "candidate-1"},
        {"idempotency_key": ""},
        {"now": NOW - timedelta(seconds=1)},
        {"now": NOW.replace(tzinfo=None)},
    ],
)
def test_invalid_submission_errors_are_explicit_and_leave_pending(store, changes):
    with pytest.raises(ValueError):
        submit(store, **changes)
    assert store.get("synthetic-review-1", now=NOW).status == "pending"


@pytest.mark.parametrize(
    "changes",
    [
        {"review_id": ""},
        {"snapshot": {"orders": {"write": True}}},
        {"expires_at": NOW},
        {"expires_at": NOW - timedelta(seconds=1)},
        {"now": NOW.replace(tzinfo=None)},
        {"expires_at": EXPIRY.replace(tzinfo=None)},
        {"timeout_seconds": 0},
        {"agent": object()},
    ],
)
def test_invalid_creation_leaves_store_empty(changes):
    result = FakeReviewStore()
    with pytest.raises(ValueError):
        create(result, **changes)
    with pytest.raises(KeyError):
        result.get("synthetic-review-1", now=NOW)


@pytest.mark.parametrize(
    "snapshot_id,matches",
    [
        ("", MATCHES),
        ("live-id", MATCHES),
        ("synthetic-v1", list(MATCHES)),
        ("synthetic-v1", ({"user_id": "driver"},)),
    ],
)
def test_snapshot_rejects_operational_shapes(snapshot_id, matches):
    with pytest.raises(ValueError):
        SyntheticCandidateSnapshot(snapshot_id, matches)


def test_unknown_review_and_backward_clock_are_explicit(store):
    with pytest.raises(KeyError):
        submit(store, review_id="missing")
    with pytest.raises(KeyError):
        store.get("missing", now=NOW)
    submit(store)
    with pytest.raises(ValueError, match="latest transition"):
        store.get("synthetic-review-1", now=NOW)
    with pytest.raises(ValueError, match="latest transition"):
        submit(store, now=NOW)


@pytest.mark.parametrize(
    "agent,reason",
    [
        (None, "AGENT_UNAVAILABLE"),
        (FakeShadowAgent(outcome="timeout"), "AGENT_TIMEOUT"),
        (FakeShadowAgent(outcome="unavailable"), "AGENT_UNAVAILABLE"),
        (FakeShadowAgent(outcome="failure"), "AGENT_FAILURE"),
        (FakeShadowAgent('{"candidate_ids": ["outsider"]}'), "MALFORMED_OUTPUT"),
        (
            FakeShadowAgent('{"candidate_ids": [], "refunds": {"approve": true}}'),
            "MALFORMED_OUTPUT",
        ),
    ],
)
def test_creation_reuses_shadow_fallback_and_can_only_prefer_existing_candidate(agent, reason):
    result = FakeReviewStore()
    pending = create(result, agent=agent)
    assert pending.recommendation.reason_code == reason
    assert pending.recommendation.candidate_ids == ("candidate-0", "candidate-1")
    assert submit(result, advisory_preference="candidate-0").status == "accepted"


def test_empty_snapshot_has_no_acceptable_preference_but_can_be_rejected():
    result = FakeReviewStore()
    snapshot = SyntheticCandidateSnapshot("synthetic-empty", ())
    pending = create(result, snapshot=snapshot)
    assert pending.recommendation.reason_code == "NO_CANDIDATES"
    with pytest.raises(ValueError, match="candidate reference"):
        submit(result, current_snapshot=snapshot)
    assert (
        submit(
            result, current_snapshot=snapshot, decision="rejected", advisory_preference=None
        ).status
        == "rejected"
    )


@pytest.mark.parametrize("decision,preference", [("accepted", "candidate-1"), ("rejected", None)])
def test_review_does_not_mutate_operational_state_or_deterministic_assignment(
    store, decision, preference
):
    db = FakeM6Db()
    db.orders["order-1"] = {"pickup_location": "SRID=4326;POINT(72.835 18.939)"}
    db.driver_matches = [
        {"user_id": "synthetic-driver-0", "distance_m": 10, "score": 9},
        {"user_id": "synthetic-driver-1", "distance_m": 20, "score": 8},
    ]
    state = {
        "assignment": {"driver": None},
        "orders": {"status": "inventory_confirmed"},
        "prices": {"quote": 100},
        "payments": {"captured": False},
        "refunds": {"manual_approval": "pending"},
        "settlements": {"approval": "pending", "pod_required": True},
        "governance": {"decision_lock": True, "grant": None},
    }
    before_db, before_state = deepcopy(vars(db)), deepcopy(state)
    submit(store, decision=decision, advisory_preference=preference)
    assert vars(db) == before_db
    assert state == before_state
    assert assign_driver({"order_id": "order-1"}, db).ok
    assert db.assignments == [("order-1", "synthetic-driver-0", "driver")]


def test_fake_store_has_no_network_or_operational_dependencies_and_is_unregistered():
    root = Path(__file__).resolve().parents[2]
    source = root / "workers/src/zippy_workers/recommendation_reviews.py"
    tree = ast.parse(source.read_text())
    imports = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports == {
        "__future__",
        "dataclasses",
        "datetime",
        "enum",
        "typing",
        "recommendations",
        "shadow_recommendations",
    }
    for folder in (root / "api", root / "workers/src/zippy_workers"):
        for path in folder.rglob("*.py"):
            if path == source or any(part.startswith("tests") for part in path.parts):
                continue
            assert "recommendation_reviews" not in path.read_text(), path


def test_entire_review_lifecycle_uses_no_network(monkeypatch):
    import socket

    async def scenario():
        def forbidden(*args, **kwargs):
            pytest.fail("fake review attempted network I/O")

        monkeypatch.setattr(socket, "socket", forbidden)
        result = FakeReviewStore()
        await result.create(
            "synthetic-review-1",
            SNAPSHOT,
            AGENT,
            now=NOW,
            expires_at=EXPIRY,
            timeout_seconds=0.01,
        )
        submit(result)
        submit(result, now=EXPIRY)
        await asyncio.sleep(0)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())
