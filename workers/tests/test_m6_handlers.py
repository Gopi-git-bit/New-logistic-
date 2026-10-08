"""M6 handler tests — order lifecycle (place_order, assign_driver, update_delivery_status)."""

import asyncio
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict

import pytest

from zippy_workers.handlers import assign_driver, place_order, update_delivery_status
from zippy_workers.recommendations import AgentRanking, recommend_drivers


class FakeRecommendationAgent:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error
        self.requests = []

    async def rank(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.output


def test_valid_recommendation_is_read_only_and_minimized():
    db = FakeM6Db()
    db.driver_matches = [
        {"user_id": "vendor-driver-1", "driver_name": "Private Name", "distance_m": 10, "score": 9},
        {"user_id": "vendor-driver-2", "distance_m": 20, "score": 8},
    ]
    before = deepcopy(vars(db))
    agent = FakeRecommendationAgent({"candidate_ids": ["candidate-1", "candidate-0"]})
    result = asyncio.run(recommend_drivers(db.driver_matches, agent, timeout_seconds=1))
    assert result.source == "agent"
    assert result.reason_code == "RECOMMENDED"
    assert result.candidate_ids == ("candidate-1", "candidate-0")
    assert vars(db) == before
    assert asdict(agent.requests[0]) == {
        "candidates": (
            {"candidate_id": "candidate-0", "distance_m": 10.0, "score": 9.0},
            {"candidate_id": "candidate-1", "distance_m": 20.0, "score": 8.0},
        )
    }
    with pytest.raises(FrozenInstanceError):
        agent.requests[0].candidates[0].score = 100


@pytest.mark.parametrize(
    "output",
    [
        None,
        "not structured output",
        AgentRanking.model_construct(candidate_ids=[["candidate-0"], "candidate-1"]),
        {"candidate_ids": ["candidate-0", "candidate-0"]},
        {"candidate_ids": ["candidate-0"]},
        {"candidate_ids": ["candidate-0", "invented-driver"]},
        {"candidate_ids": [0, 1]},
        {"candidate_ids": ["candidate-0", "candidate-1"], "assign_driver": True},
        {"candidate_ids": ["candidate-0", "candidate-1"], "refund_approved": True},
        {"candidate_ids": ["candidate-0", "candidate-1"], "settlement_status": "released"},
    ],
)
def test_malformed_or_mutating_output_uses_deterministic_fallback(output):
    db = FakeM6Db()
    db.driver_matches = [{"user_id": "driver-1"}, {"user_id": "driver-2"}]
    before = deepcopy(vars(db))
    result = asyncio.run(
        recommend_drivers(
            db.driver_matches,
            FakeRecommendationAgent(output),
            timeout_seconds=1,
        )
    )
    assert result.source == "deterministic"
    assert result.reason_code == "MALFORMED_OUTPUT"
    assert result.candidate_ids == ("candidate-0", "candidate-1")
    assert vars(db) == before


@pytest.mark.parametrize(
    "agent,reason",
    [
        (None, "AGENT_UNAVAILABLE"),
        (FakeRecommendationAgent(error=ConnectionError("unavailable")), "AGENT_UNAVAILABLE"),
        (FakeRecommendationAgent(error=RuntimeError("failure")), "AGENT_FAILURE"),
    ],
)
def test_unavailable_agent_preserves_shortlist(agent, reason):
    result = asyncio.run(recommend_drivers([{}, {}], agent, timeout_seconds=1))
    assert result.source == "deterministic"
    assert result.reason_code == reason
    assert result.candidate_ids == ("candidate-0", "candidate-1")


@pytest.mark.parametrize(
    "agent,source,reason",
    [
        (None, "deterministic", "AGENT_UNAVAILABLE"),
        (FakeRecommendationAgent({"candidate_ids": ["candidate-0"]}), "agent", "RECOMMENDED"),
    ],
)
def test_oversized_features_do_not_interrupt_recommendations(agent, source, reason):
    db = FakeM6Db()
    db.driver_matches = [{"distance_m": 10**1000, "score": -(10**1000)}]
    before = deepcopy(vars(db))
    result = asyncio.run(recommend_drivers(db.driver_matches, agent, timeout_seconds=1))
    assert result.source == source
    assert result.reason_code == reason
    assert result.candidate_ids == ("candidate-0",)
    assert vars(db) == before
    if agent is not None:
        assert asdict(agent.requests[0]) == {
            "candidates": ({"candidate_id": "candidate-0", "distance_m": None, "score": None},)
        }


def test_agent_timeout_cancels_adapter_and_uses_deterministic_fallback():
    class HangingAgent:
        cancelled = False

        async def rank(self, request):
            try:
                await asyncio.Future()
            finally:
                self.cancelled = True

    agent = HangingAgent()
    result = asyncio.run(recommend_drivers([{}, {}], agent, timeout_seconds=0.001))
    assert agent.cancelled
    assert result.reason_code == "AGENT_TIMEOUT"
    assert result.source == "deterministic"
    assert result.candidate_ids == ("candidate-0", "candidate-1")


def test_empty_shortlist_never_calls_agent():
    agent = FakeRecommendationAgent(error=AssertionError("must not be called"))
    result = asyncio.run(recommend_drivers([], agent, timeout_seconds=1))
    assert result.reason_code == "NO_CANDIDATES"
    assert result.candidate_ids == ()
    assert not agent.requests


@pytest.mark.parametrize("late_error", [None, RuntimeError("late adapter failure")])
def test_timeout_fallback_does_not_wait_for_suppressed_cancellation(late_error):
    async def scenario():
        cancellation_seen = asyncio.Event()
        release_cleanup = asyncio.Event()
        finished = asyncio.Event()
        errors = []
        asyncio.get_running_loop().set_exception_handler(
            lambda loop, context: errors.append(context)
        )

        class SlowCancellationAgent:
            async def rank(self, request):
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    cancellation_seen.set()
                    await release_cleanup.wait()
                    if late_error is not None:
                        raise late_error from None
                    return {"candidate_ids": ["candidate-1", "candidate-0"]}
                finally:
                    finished.set()

        db = FakeM6Db()
        db.driver_matches = [{"user_id": "driver-1"}, {"user_id": "driver-2"}]
        before = deepcopy(vars(db))
        try:
            result = await asyncio.wait_for(
                recommend_drivers(
                    db.driver_matches, SlowCancellationAgent(), timeout_seconds=0.001
                ),
                timeout=0.2,
            )
            assert result.reason_code == "AGENT_TIMEOUT"
            assert result.source == "deterministic"
            assert result.candidate_ids == ("candidate-0", "candidate-1")
            await asyncio.wait_for(cancellation_seen.wait(), timeout=0.2)
            assert not finished.is_set()
        finally:
            release_cleanup.set()
        await asyncio.wait_for(finished.wait(), timeout=0.2)
        assert result.source == "deterministic"
        assert vars(db) == before
        assert not errors

    asyncio.run(scenario())


def test_recommendation_cannot_override_autonomous_assignment():
    db = FakeM6Db()
    db.orders["order-1"] = {"pickup_location": "SRID=4326;POINT(72.835 18.939)"}
    db.driver_matches = [{"user_id": "driver-1"}, {"user_id": "driver-2"}]
    agent = FakeRecommendationAgent({"candidate_ids": ["candidate-1", "candidate-0"]})
    recommendation = asyncio.run(recommend_drivers(db.driver_matches, agent, timeout_seconds=1))
    assert recommendation.candidate_ids[0] == "candidate-1"
    assert not db.assignments and not db.transitions and not db.payment_validations and not db.tasks
    result = assign_driver({"order_id": "order-1"}, db)
    assert result.ok
    assert db.assignments == [("order-1", "driver-1", "driver")]
    assert db.transitions == [("order-1", "driver_assigned")]


# ---------------------------------------------------------------------------
# Fake Db extensions for M6
# ---------------------------------------------------------------------------


class FakeM6Db:
    """Fake Db with all M6 protocol methods."""

    def __init__(self):
        self.transitions: list[tuple[str, str]] = []
        self.tasks: list[tuple[str, str, dict]] = []
        self.quotes: dict[str, dict | None] = {}
        self.driver_matches: list[dict] = []
        self.assignments: list[tuple[str, str, str]] = []
        self.payment_validations: list[tuple[str, float, float]] = []
        self.orders: dict[str, dict] = {}

    def transition_order(self, order_id, new_status):
        self.transitions.append((order_id, new_status))

    def enqueue_task(self, agent, task_type, payload):
        self.tasks.append((agent, task_type, payload))

    def generate_quote(self, order_id: str) -> dict | None:
        return self.quotes.get(
            order_id,
            {
                "vehicle_class": "LCV",
                "rate_per_km": 25.0,
                "freight_amount": 3750.0,
                "toll_amount": 120.0,
                "loading_amount": 112.5,
                "tax_amount": 199.13,
                "total_amount": 4181.63,
            },
        )

    def match_drivers(
        self,
        pickup_wkt: str,
        radius_m: float,
        limit: int,
        required_class: str | None,
        cargo_weight: float | None,
    ) -> list[dict]:
        return self.driver_matches

    def assign_provider(self, order_id: str, provider_id: str, provider_type: str) -> None:
        self.assignments.append((order_id, provider_id, provider_type))

    def validate_payment_plan(self, mode: str, total: float, advance: float) -> bool:
        self.payment_validations.append((mode, total, advance))
        if mode == "full":
            return advance == total
        if mode == "partial":
            return advance >= total * 0.5
        # to_pay
        return advance == 0

    def get_order(self, order_id: str) -> dict | None:
        return self.orders.get(order_id)


# ---------------------------------------------------------------------------
# place_order tests
# ---------------------------------------------------------------------------


def test_place_order_happy_path():
    db = FakeM6Db()
    r = place_order(
        {"order_id": "o-1", "customer_id": "c-1", "payment_mode": "full"},
        db,
    )
    assert r.ok, r.detail
    assert r.detail["total_amount"] == 4181.63
    assert r.detail["payment_mode"] == "full"
    assert ("o-1", "pending") in db.transitions


def test_place_order_missing_fields():
    db = FakeM6Db()
    r = place_order({}, db)
    assert not r.ok and "missing" in r.detail["error"]


def test_place_order_invalid_payment_plan():
    db = FakeM6Db()
    r = place_order(
        {"order_id": "o-2", "customer_id": "c-1", "payment_mode": "partial", "advance_amount": 100},
        db,
    )
    assert not r.ok and "invalid_payment_plan" in r.detail["error"]


def test_place_order_idempotent_already_pending():
    class AlreadyPending(FakeM6Db):
        def transition_order(self, oid, ns):
            raise RuntimeError("Invalid transition from pending")

    db = AlreadyPending()
    r = place_order({"order_id": "o-3", "customer_id": "c-1"}, db)
    assert r.ok  # idempotent


def test_place_order_quote_failure():
    class NoQuote(FakeM6Db):
        def generate_quote(self, oid):
            return None

    db = NoQuote()
    r = place_order({"order_id": "o-4", "customer_id": "c-1"}, db)
    assert not r.ok and "quote_generation_failed" in r.detail["error"]


# ---------------------------------------------------------------------------
# assign_driver tests
# ---------------------------------------------------------------------------


def test_assign_driver_happy_path():
    db = FakeM6Db()
    db.orders["o-10"] = {
        "order_id": "o-10",
        "pickup_location": "SRID=4326;POINT(72.835 18.939)",
        "pickup_latitude": 18.939,
        "pickup_longitude": 72.835,
    }
    db.driver_matches = [
        {
            "user_id": "u-d1",
            "driver_id": "d-1",
            "driver_name": "Ravi Kumar",
            "rating": 4.5,
            "vehicle_id": "v-1",
            "vehicle_type": "LCV",
            "capacity_tons": 2.5,
            "distance_m": 1500.0,
            "score": 44.25,
        },
    ]
    r = assign_driver({"order_id": "o-10"}, db)
    assert r.ok, r.detail
    assert r.detail["driver_name"] == "Ravi Kumar"
    assert db.assignments == [("o-10", "u-d1", "driver")]
    assert ("o-10", "driver_assigned") in db.transitions


def test_assign_driver_no_order():
    db = FakeM6Db()
    r = assign_driver({}, db)
    assert not r.ok and "missing order_id" in r.detail["error"]


def test_assign_driver_order_not_found():
    db = FakeM6Db()
    r = assign_driver({"order_id": "o-notfound"}, db)
    assert not r.ok and "order_not_found" in r.detail["error"]


def test_assign_driver_no_match():
    db = FakeM6Db()
    db.orders["o-11"] = {
        "order_id": "o-11",
        "pickup_location": "SRID=4326;POINT(72.835 18.939)",
    }
    db.driver_matches = []
    r = assign_driver({"order_id": "o-11"}, db)
    assert r.ok
    assert r.detail["note"] == "no_available_drivers"
    assert not db.assignments


def test_assign_driver_fallback_to_latlng():
    db = FakeM6Db()
    db.orders["o-12"] = {
        "order_id": "o-12",
        "pickup_location": None,
        "pickup_latitude": 18.94,
        "pickup_longitude": 72.84,
    }
    db.driver_matches = [
        {
            "user_id": "u-d2",
            "driver_id": "d-2",
            "driver_name": "Test Driver",
            "rating": 4.0,
            "vehicle_id": "v-2",
            "vehicle_type": "MCV",
            "capacity_tons": 9.0,
            "distance_m": 5000.0,
            "score": 35.0,
        },
    ]
    r = assign_driver({"order_id": "o-12"}, db)
    assert r.ok
    assert db.assignments[0][1] == "u-d2"


def test_assign_driver_no_pickup_at_all():
    db = FakeM6Db()
    db.orders["o-13"] = {
        "order_id": "o-13",
        "pickup_location": None,
        "pickup_latitude": None,
        "pickup_longitude": None,
    }
    r = assign_driver({"order_id": "o-13"}, db)
    assert not r.ok and "no_pickup_location" in r.detail["error"]


def test_assign_driver_idempotent_already_assigned():
    class AlreadyAssigned(FakeM6Db):
        def transition_order(self, oid, ns):
            raise RuntimeError("Invalid transition from driver_assigned")

    db = AlreadyAssigned()
    db.orders["o-14"] = {
        "order_id": "o-14",
        "pickup_location": "SRID=4326;POINT(72.835 18.939)",
    }
    db.driver_matches = [
        {
            "user_id": "u-d3",
            "driver_id": "d-3",
            "driver_name": "Idem Driver",
            "rating": 4.2,
            "vehicle_id": "v-3",
            "vehicle_type": "LCV",
            "capacity_tons": 2.5,
            "distance_m": 2000.0,
            "score": 41.0,
        },
    ]
    r = assign_driver({"order_id": "o-14"}, db)
    assert r.ok  # idempotent


# ---------------------------------------------------------------------------
# update_delivery_status tests
# ---------------------------------------------------------------------------


def test_delivery_status_pickup_advances_to_in_transit():
    db = FakeM6Db()
    r = update_delivery_status({"order_id": "o-20", "action": "pickup"}, db)
    assert r.ok and r.detail["advanced_to"] == "in_transit"
    assert ("o-20", "in_transit") in db.transitions


def test_delivery_status_delivered():
    db = FakeM6Db()
    r = update_delivery_status({"order_id": "o-21", "action": "delivered"}, db)
    assert r.ok and r.detail["advanced_to"] == "delivered"


def test_delivery_status_missing_fields():
    db = FakeM6Db()
    r = update_delivery_status({}, db)
    assert not r.ok and "missing" in r.detail["error"]


def test_delivery_status_unknown_action():
    db = FakeM6Db()
    r = update_delivery_status({"order_id": "o-22", "action": "unknown"}, db)
    assert not r.ok and "unknown action" in r.detail["error"]


def test_delivery_status_idempotent_noop():
    class AlreadyDelivered(FakeM6Db):
        def transition_order(self, oid, ns):
            raise RuntimeError("Invalid transition from delivered")

    db = AlreadyDelivered()
    r = update_delivery_status({"order_id": "o-23", "action": "delivered"}, db)
    assert r.ok and r.detail.get("note") == "idempotent no-op"
