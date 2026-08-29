"""M6 handler tests — order lifecycle (place_order, assign_driver, update_delivery_status)."""

from zippy_workers.handlers import assign_driver, place_order, update_delivery_status

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
