from __future__ import annotations

import os
import selectors
import subprocess
import tempfile
import unittest
from unittest import mock

from homenettopo.commands import (
    STDOUT_LIMIT,
    CommandError,
    CommandKind,
    CommandSpec,
    _stop_process,
    interfaces_spec,
    nmap_spec,
    resolve_nmap,
    run_command,
)


class FakeProcess:
    def __init__(self, returncode=0, *, timeout_on_first_wait=False):
        self.stdout = object()
        self.stderr = object()
        self.returncode = returncode
        self.timeout_on_first_wait = timeout_on_first_wait
        self.wait_calls = []
        self.terminated = False
        self.killed = False
        self.finished = False

    def poll(self):
        return self.returncode if self.finished else None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if self.timeout_on_first_wait and len(self.wait_calls) == 1:
            raise subprocess.TimeoutExpired("fake", timeout)
        self.finished = True
        return self.returncode


class FakeKey:
    def __init__(self, fileobj, fd, data):
        self.fileobj = fileobj
        self.fd = fd
        self.data = data


class FakeSelector:
    def __init__(self):
        self.keys = {}
        self.closed = False

    def register(self, fileobj, _event, data):
        self.keys[fileobj] = FakeKey(fileobj, len(self.keys) + 10, data)

    def unregister(self, fileobj):
        self.keys.pop(fileobj)

    def get_map(self):
        return self.keys

    def select(self, timeout=None):
        return [(key, selectors.EVENT_READ) for key in list(self.keys.values())]

    def close(self):
        self.closed = True


class CommandTests(unittest.TestCase):
    def test_passive_command_is_absolute_and_typed(self):
        spec = interfaces_spec()
        self.assertEqual(spec.kind, CommandKind.INTERFACES)
        self.assertEqual(spec.argv, ("/sbin/ifconfig", "-a"))

    def test_resolves_explicit_executable_and_reports_source_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "nmap")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\n")
            os.chmod(path, 0o700)
            resolution = resolve_nmap(path)
            self.assertEqual(resolution.source, "explicit")
            self.assertEqual(resolution.path, os.path.realpath(path))

    @mock.patch("homenettopo.commands._verified_executable", return_value="/opt/homebrew/bin/nmap")
    def test_nmap_arguments_are_fixed(self, _verified):
        spec = nmap_spec("/opt/homebrew/bin/nmap", ["192.168.1.0/24"], 30)
        self.assertEqual(spec.argv[1:9], ("-sn", "-n", "--max-retries", "1", "--host-timeout", "5s", "-oX", "-"))
        self.assertEqual(spec.argv[-1], "192.168.1.0/24")
        self.assertEqual(spec.timeout_seconds, 30)

    @mock.patch("homenettopo.commands._verified_executable", return_value="/opt/homebrew/bin/nmap")
    def test_nmap_keeps_adjacent_targets_separate(self, _verified):
        spec = nmap_spec(
            "/opt/homebrew/bin/nmap",
            ["192.168.1.0/25", "192.168.1.128/25"],
            30,
        )
        self.assertEqual(spec.argv[9:], ("192.168.1.0/25", "192.168.1.128/25"))

    @mock.patch("homenettopo.commands._verified_executable", return_value="/opt/homebrew/bin/nmap")
    def test_nmap_preserves_contained_targets_from_distinct_phase_b_owners(self, _verified):
        spec = nmap_spec(
            "/opt/homebrew/bin/nmap",
            ["192.168.1.0/24", "192.168.1.0/25", "192.168.1.0/25"],
            30,
        )
        self.assertEqual(spec.argv[9:], ("192.168.1.0/24", "192.168.1.0/25"))

    @mock.patch("homenettopo.commands._verified_executable", return_value="/opt/homebrew/bin/nmap")
    def test_nmap_rejects_option_injection_non_rfc1918_special_large_union_and_non_integer_timeout(self, _verified):
        cases = (
            (["--script"], 30),
            (["8.8.8.0/24"], 30),
            (["127.0.0.0/8"], 30),
            (["169.254.0.0/16"], 30),
            (["192.0.0.0/24"], 30),
            (["198.18.0.0/15"], 30),
            (["192.0.2.0/24"], 30),
            (["10.0.0.0/21"], 30),
            (["10.0.0.0/24"], 30.0),
        )
        for targets, timeout in cases:
            with self.subTest(targets=targets, timeout=timeout), self.assertRaises(CommandError):
                nmap_spec("/opt/homebrew/bin/nmap", targets, timeout)

    def test_generic_absolute_command_spec_is_rejected_before_popen(self):
        spec = CommandSpec(CommandKind.INTERFACES, ("/bin/echo", "unsafe"), 5)
        with mock.patch("homenettopo.commands.subprocess.Popen") as popen, self.assertRaises(CommandError):
            run_command(spec)
        popen.assert_not_called()

    def test_popen_failure_is_normalized(self):
        with mock.patch("homenettopo.commands.subprocess.Popen", side_effect=OSError("missing")), self.assertRaises(CommandError) as raised:
            run_command(interfaces_spec())
        self.assertEqual(raised.exception.code, "dependency_unavailable")

    def test_timeout_terminates_the_process(self):
        process = FakeProcess()
        selector = FakeSelector()
        with (
            mock.patch("homenettopo.commands.subprocess.Popen", return_value=process),
            mock.patch("homenettopo.commands.selectors.DefaultSelector", return_value=selector),
            mock.patch("homenettopo.commands.time.monotonic", side_effect=[0.0, 6.0]),
            self.assertRaises(CommandError) as raised,
        ):
            run_command(interfaces_spec())
        self.assertEqual(raised.exception.code, "command_timeout")
        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)
        self.assertTrue(selector.closed)

    def test_output_limit_terminates_the_process(self):
        process = FakeProcess()
        selector = FakeSelector()
        with (
            mock.patch("homenettopo.commands.subprocess.Popen", return_value=process),
            mock.patch("homenettopo.commands.selectors.DefaultSelector", return_value=selector),
            mock.patch("homenettopo.commands.os.read", return_value=b"x" * (STDOUT_LIMIT + 1)),
            mock.patch("homenettopo.commands.time.monotonic", return_value=0.0),
            self.assertRaises(CommandError) as raised,
        ):
            run_command(interfaces_spec())
        self.assertEqual(raised.exception.code, "collection_failed")
        self.assertTrue(process.terminated)

    def test_nonzero_exit_is_normalized_with_returncode(self):
        process = FakeProcess(returncode=7)
        selector = FakeSelector()
        with (
            mock.patch("homenettopo.commands.subprocess.Popen", return_value=process),
            mock.patch("homenettopo.commands.selectors.DefaultSelector", return_value=selector),
            mock.patch("homenettopo.commands.os.read", side_effect=[b"", b""]),
            mock.patch("homenettopo.commands.time.monotonic", return_value=0.0),
            self.assertRaises(CommandError) as raised,
        ):
            run_command(interfaces_spec())
        self.assertEqual(raised.exception.code, "collection_failed")
        self.assertEqual(raised.exception.returncode, 7)

    def test_stop_process_escalates_from_terminate_to_kill(self):
        process = FakeProcess(timeout_on_first_wait=True)
        _stop_process(process)
        self.assertTrue(process.terminated)
        self.assertTrue(process.killed)
        self.assertEqual(len(process.wait_calls), 2)


if __name__ == "__main__":
    unittest.main()
