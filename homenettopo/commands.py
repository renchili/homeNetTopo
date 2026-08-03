"""Approved command construction and bounded shell-free execution."""

from __future__ import annotations

import os
import selectors
import shutil
import stat
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

PASSIVE_TIMEOUT_SECONDS = 5
STDOUT_LIMIT = 2 * 1024 * 1024
STDERR_LIMIT = 64 * 1024
KILL_GRACE_SECONDS = 2
NMAP_HOST_TIMEOUT_SECONDS = 5


class CommandError(RuntimeError):
    def __init__(self, code: str, message: str, *, returncode: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.returncode = returncode


class CommandKind(str, Enum):
    INTERFACES = "interfaces"
    ROUTES = "routes"
    NEIGHBORS = "neighbors"
    NMAP = "nmap"


@dataclass(frozen=True)
class CommandSpec:
    kind: CommandKind
    argv: tuple[str, ...]
    timeout_seconds: int


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int
    duration_ms: int


@dataclass(frozen=True)
class NmapResolution:
    path: str | None
    source: str


def interfaces_spec() -> CommandSpec:
    return CommandSpec(CommandKind.INTERFACES, ("/sbin/ifconfig", "-a"), PASSIVE_TIMEOUT_SECONDS)


def routes_spec() -> CommandSpec:
    return CommandSpec(CommandKind.ROUTES, ("/usr/sbin/netstat", "-rn", "-f", "inet"), PASSIVE_TIMEOUT_SECONDS)


def neighbors_spec() -> CommandSpec:
    return CommandSpec(CommandKind.NEIGHBORS, ("/usr/sbin/arp", "-an"), PASSIVE_TIMEOUT_SECONDS)


def _verified_executable(candidate: str | None) -> str | None:
    if not candidate:
        return None
    path = os.path.realpath(candidate)
    try:
        mode = os.stat(path).st_mode
    except OSError:
        return None
    if not stat.S_ISREG(mode) or not os.access(path, os.X_OK):
        return None
    return path


def resolve_nmap(explicit_path: str | None = None) -> NmapResolution:
    candidates = (
        (explicit_path, "explicit"),
        ("/opt/homebrew/bin/nmap", "homebrew_arm64"),
        ("/usr/local/bin/nmap", "homebrew_intel"),
        (shutil.which("nmap"), "path"),
    )
    for candidate, source in candidates:
        verified = _verified_executable(candidate)
        if verified:
            return NmapResolution(verified, source)
    return NmapResolution(None, "unavailable")


def nmap_spec(path: str, networks: Iterable[str], operation_timeout_seconds: int) -> CommandSpec:
    verified = _verified_executable(path)
    if not verified or verified != os.path.realpath(path):
        raise CommandError("dependency_unavailable", "Nmap is unavailable.")
    targets = tuple(networks)
    if not targets:
        raise CommandError("invalid_target", "At least one validated target is required.")
    argv = (
        verified,
        "-sn",
        "-n",
        "--max-retries",
        "1",
        "--host-timeout",
        f"{NMAP_HOST_TIMEOUT_SECONDS}s",
        "-oX",
        "-",
        *targets,
    )
    return CommandSpec(CommandKind.NMAP, argv, operation_timeout_seconds)


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_command(spec: CommandSpec) -> CommandResult:
    if not spec.argv or not os.path.isabs(spec.argv[0]):
        raise CommandError("collection_failed", "Command specification is not approved.")
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            spec.argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C"},
            close_fds=True,
        )
    except OSError as exc:
        raise CommandError("dependency_unavailable", "A required executable is unavailable.") from exc

    assert process.stdout is not None and process.stderr is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, ("stdout", STDOUT_LIMIT))
    selector.register(process.stderr, selectors.EVENT_READ, ("stderr", STDERR_LIMIT))
    output = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = started + spec.timeout_seconds

    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _stop_process(process)
                raise CommandError("command_timeout", "The collection command timed out.")
            events = selector.select(timeout=min(remaining, 0.2))
            if not events and process.poll() is not None:
                events = [(key, selectors.EVENT_READ) for key in list(selector.get_map().values())]
            for key, _ in events:
                stream_name, limit = key.data
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                output[stream_name].extend(chunk)
                if len(output[stream_name]) > limit:
                    _stop_process(process)
                    raise CommandError("collection_failed", "Command output exceeded the configured limit.")
        remaining = max(0.0, deadline - time.monotonic())
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            _stop_process(process)
            raise CommandError("command_timeout", "The collection command timed out.") from exc
    finally:
        selector.close()

    duration_ms = int((time.monotonic() - started) * 1000)
    stdout = output["stdout"].decode("utf-8", errors="replace")
    stderr = output["stderr"].decode("utf-8", errors="replace")
    if returncode != 0:
        raise CommandError("collection_failed", "A collection command failed.", returncode=returncode)
    return CommandResult(stdout, stderr, returncode, duration_ms)
