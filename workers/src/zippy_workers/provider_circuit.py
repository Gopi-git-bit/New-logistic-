"""Private, persistent one-failure latch; never authorizes provider fallback."""

from __future__ import annotations

import fcntl
import os
import re
import stat
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .capabilities import UnauthorizedCapability


class CircuitError(UnauthorizedCapability):
    pass


class CircuitFailure(Enum):
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate-limited"
    SAFETY = "safety"


@dataclass(frozen=True)
class CircuitPermit:
    token: str = field(repr=False)


class StrictProviderCircuit:
    """Single in-flight request, latched open on any failure, no automatic reset.

    A crashed request leaves its reservation and blocks later invocations. State
    belongs to the trusted target; this is not protection from hostile Python or
    an operator deleting its own state. The directory must already be private.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    @staticmethod
    def _private_file(fd: int) -> None:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise CircuitError("OMS_STAGING_CIRCUIT_STORE_UNSAFE")

    @contextmanager
    def _locked(self) -> Iterator[int]:
        directory_fd = lock_fd = -1
        try:
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            info = os.fstat(directory_fd)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise CircuitError("OMS_STAGING_CIRCUIT_STORE_UNSAFE")
            lock_fd = os.open(
                "deepseek-circuit.lock",
                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                0o600,
                dir_fd=directory_fd,
            )
            self._private_file(lock_fd)
            # Contention denies instead of waiting beyond the invocation budget.
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield directory_fd
        except OSError:
            raise CircuitError("OMS_STAGING_CIRCUIT_STORE_UNAVAILABLE") from None
        finally:
            if lock_fd >= 0:
                os.close(lock_fd)
            if directory_fd >= 0:
                os.close(directory_fd)

    @staticmethod
    def _exists(directory_fd: int, name: str) -> bool:
        try:
            os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True

    def reserve(self) -> CircuitPermit:
        with self._locked() as directory_fd:
            if self._exists(directory_fd, "deepseek-circuit.open"):
                raise CircuitError("OMS_STAGING_CIRCUIT_OPEN")
            if self._exists(directory_fd, "deepseek-circuit.releasing"):
                raise CircuitError("OMS_STAGING_CIRCUIT_RELEASE_UNVERIFIED")
            if self._exists(directory_fd, "deepseek-circuit.active"):
                raise CircuitError("OMS_STAGING_CIRCUIT_BUSY_OR_ABANDONED")
            permit = CircuitPermit(uuid.uuid4().hex)
            fd = os.open(
                "deepseek-circuit.active",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_fd,
            )
            try:
                self._private_file(fd)
                if os.write(fd, permit.token.encode("ascii")) != 32:
                    raise CircuitError("OMS_STAGING_CIRCUIT_STORE_UNAVAILABLE")
                os.fsync(fd)
                os.fsync(directory_fd)
            finally:
                os.close(fd)
            return permit

    def finish(self, permit: CircuitPermit, failure: CircuitFailure | None) -> None:
        if (
            type(permit) is not CircuitPermit
            or type(permit.token) is not str
            or (re.fullmatch(r"[0-9a-f]{32}", permit.token) is None)
            or (failure is not None and type(failure) is not CircuitFailure)
        ):
            raise CircuitError("OMS_STAGING_CIRCUIT_INVALID_OUTCOME")
        with self._locked() as directory_fd:
            fd = os.open(
                "deepseek-circuit.active",
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=directory_fd,
            )
            try:
                self._private_file(fd)
                token = os.read(fd, 33)
            finally:
                os.close(fd)
            if token != permit.token.encode("ascii"):
                raise CircuitError("OMS_STAGING_CIRCUIT_PERMIT_MISMATCH")
            if failure is None:
                # Persist a blocking guard before removing the sole reservation.
                # Release failures must not need a recovery write to deny later
                # runs: a failing store may reject that write too.
                fd = os.open(
                    "deepseek-circuit.releasing",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=directory_fd,
                )
                try:
                    self._private_file(fd)
                    if os.write(fd, token) != len(token):
                        raise CircuitError("OMS_STAGING_CIRCUIT_STORE_UNAVAILABLE")
                    os.fsync(fd)
                    os.fsync(directory_fd)
                finally:
                    os.close(fd)
            if failure is not None:
                # The existence of even an incomplete marker latches the circuit.
                # Never remove a failure marker or clear abandoned reservations.
                fd = os.open(
                    "deepseek-circuit.open",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=directory_fd,
                )
                try:
                    self._private_file(fd)
                    data = failure.value.encode("ascii")
                    if os.write(fd, data) != len(data):
                        raise CircuitError("OMS_STAGING_CIRCUIT_STORE_UNAVAILABLE")
                    os.fsync(fd)
                    os.fsync(directory_fd)
                finally:
                    os.close(fd)
            os.unlink("deepseek-circuit.active", dir_fd=directory_fd)
            os.fsync(directory_fd)
            if failure is None:
                os.unlink("deepseek-circuit.releasing", dir_fd=directory_fd)
                # Intentionally no final fsync: the active removal is already
                # durable. A crash may restore this guard and conservatively
                # deny a later run, but cannot erase an error's blocking state.

    def assert_fallback_authorized(self) -> None:
        # No trusted OpenRouter/Qwen policy or issuer exists in this preparation.
        # Circuit-open state, cooldowns and a fallback key cannot grant authority.
        raise CircuitError("OMS_STAGING_FALLBACK_NOT_AUTHORIZED")
