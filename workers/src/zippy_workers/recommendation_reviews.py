"""Unregistered, fake-only advisory reviews; no operational or governance authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Literal

from .recommendations import RecommendationResult
from .shadow_recommendations import FakeShadowAgent, SyntheticMatch, evaluate_shadow


class FakeReviewer(Enum):
    HUMAN_A = "synthetic-human-a"
    HUMAN_B = "synthetic-human-b"
    AGENT = "synthetic-agent"
    OUTSIDER = "synthetic-outsider"


class UnauthorizedReviewer(PermissionError):
    pass


class ReviewConflict(ValueError):
    pass


class StaleReview(ValueError):
    pass


class ExpiredReview(ValueError):
    pass


def _nonempty(value: str, field: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")


def _timestamp(value: datetime) -> None:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware datetimes")


@dataclass(frozen=True)
class SyntheticCandidateSnapshot:
    """Version plus exact ordered features; positional candidate IDs alone are insufficient."""

    snapshot_id: str
    matches: tuple[SyntheticMatch, ...]

    def __post_init__(self) -> None:
        _nonempty(self.snapshot_id, "snapshot_id")
        if not self.snapshot_id.startswith("synthetic-"):
            raise ValueError("snapshot_id must have the synthetic- prefix")
        if type(self.matches) is not tuple or any(
            type(match) is not SyntheticMatch for match in self.matches
        ):
            raise ValueError("only a tuple of SyntheticMatch fixtures is accepted")


ReviewStatus = Literal["pending", "accepted", "rejected", "expired"]
ReviewDecision = Literal["accepted", "rejected"]


@dataclass(frozen=True)
class RecommendationReview:
    review_id: str
    snapshot: SyntheticCandidateSnapshot
    recommendation: RecommendationResult
    created_at: datetime
    expires_at: datetime
    updated_at: datetime
    status: ReviewStatus = "pending"
    reviewer: FakeReviewer | None = None
    advisory_preference: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class _Creation:
    snapshot: SyntheticCandidateSnapshot
    agent: FakeShadowAgent | None
    created_at: datetime
    expires_at: datetime
    timeout_seconds: float


@dataclass(frozen=True)
class _Submission:
    review_id: str
    snapshot: SyntheticCandidateSnapshot
    reviewer: FakeReviewer
    decision: ReviewDecision
    advisory_preference: str | None


class FakeReviewStore:
    """Single-process test storage, with caller-supplied synthetic time and identity.

    Review IDs deduplicate creation; submission keys deduplicate decisions across
    the whole store. Neither namespace is a production authorization mechanism.
    """

    def __init__(self) -> None:
        self._records: dict[str, RecommendationReview] = {}
        self._creations: dict[str, tuple[_Creation, RecommendationReview]] = {}
        self._submissions: dict[str, tuple[_Submission, RecommendationReview]] = {}

    async def create(
        self,
        review_id: str,
        snapshot: SyntheticCandidateSnapshot,
        agent: FakeShadowAgent | None,
        *,
        now: datetime,
        expires_at: datetime,
        timeout_seconds: float,
    ) -> RecommendationReview:
        _nonempty(review_id, "review_id")
        if type(snapshot) is not SyntheticCandidateSnapshot:
            raise ValueError("only a SyntheticCandidateSnapshot fixture is accepted")
        if agent is not None and type(agent) is not FakeShadowAgent:
            raise ValueError("only the built-in fake shadow agent is accepted")
        _timestamp(now)
        _timestamp(expires_at)
        if expires_at <= now:
            raise ValueError("expires_at must be after creation time")
        creation = _Creation(snapshot, agent, now, expires_at, timeout_seconds)
        if review_id in self._creations:
            return self._replay_creation(review_id, creation)
        comparison = await evaluate_shadow(
            snapshot.matches,
            agent,
            agent_name="order_management",
            action="recommend_drivers",
            tool="recommend_drivers",
            timeout_seconds=timeout_seconds,
        )
        # Concurrent identical creations must not overwrite an intervening decision.
        if review_id in self._creations:
            return self._replay_creation(review_id, creation)
        record = RecommendationReview(
            review_id, snapshot, comparison.advisory, now, expires_at, now
        )
        self._records[review_id] = record
        self._creations[review_id] = (creation, record)
        return record

    def _replay_creation(self, review_id: str, creation: _Creation) -> RecommendationReview:
        previous, result = self._creations[review_id]
        if previous != creation:
            raise ReviewConflict("review_id reused with different creation inputs")
        return result

    def get(self, review_id: str, *, now: datetime) -> RecommendationReview:
        record = self._records[review_id]
        self._validate_time(record, now)
        if record.status == "pending" and now >= record.expires_at:
            record = replace(record, status="expired", updated_at=record.expires_at)
            self._records[review_id] = record
        return record

    @staticmethod
    def _validate_time(record: RecommendationReview, now: datetime) -> None:
        _timestamp(now)
        if now < record.updated_at:
            raise ValueError("review time cannot precede its latest transition")

    def review(
        self,
        review_id: str,
        current_snapshot: SyntheticCandidateSnapshot,
        reviewer: FakeReviewer,
        decision: ReviewDecision,
        *,
        advisory_preference: str | None = None,
        idempotency_key: str,
        now: datetime,
    ) -> RecommendationReview:
        if type(reviewer) is not FakeReviewer or reviewer not in (
            FakeReviewer.HUMAN_A,
            FakeReviewer.HUMAN_B,
        ):
            raise UnauthorizedReviewer("only explicit fake human reviewers may review")
        _nonempty(idempotency_key, "idempotency_key")
        record = self._records[review_id]
        self._validate_time(record, now)
        if (
            type(current_snapshot) is not SyntheticCandidateSnapshot
            or current_snapshot != record.snapshot
        ):
            raise StaleReview("review does not match the exact current candidate snapshot")
        if decision not in ("accepted", "rejected"):
            raise ValueError("decision must be accepted or rejected")
        if decision == "accepted":
            if (
                type(advisory_preference) is not str
                or advisory_preference not in record.recommendation.candidate_ids
            ):
                raise ValueError("acceptance requires an advisory candidate reference")
        elif advisory_preference is not None:
            raise ValueError("rejection cannot record an advisory preference")
        submission = _Submission(
            review_id, current_snapshot, reviewer, decision, advisory_preference
        )
        if idempotency_key in self._submissions:
            previous, result = self._submissions[idempotency_key]
            if previous != submission:
                raise ReviewConflict("idempotency_key reused with different review inputs")
            return result
        record = self.get(review_id, now=now)
        if record.status == "expired":
            raise ExpiredReview("recommendation review has expired")
        if record.status != "pending":
            raise ReviewConflict("terminal review cannot be changed or reviewed again")
        result = replace(
            record,
            status=decision,
            reviewer=reviewer,
            advisory_preference=advisory_preference,
            idempotency_key=idempotency_key,
            updated_at=now,
        )
        self._records[review_id] = result
        self._submissions[idempotency_key] = (submission, result)
        return result
