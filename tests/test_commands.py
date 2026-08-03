from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from homenettopo.commands import CommandError, CommandKind, CommandSpec, interfaces_spec, nmap_spec, resolve_nmap, run_command


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
    def test_nmap_rejects_option_injection_public_and_large_union(self, _verified):
        for targets in (["--script"], ["8.8.8.0/24"], ["10.0.0.0/21"]):
            with self.subTest(targets=targets), self.assertRaises(CommandError):
                nmap_spec("/opt/homebrew/bin/nmap", targets, 30)

    def test_generic_absolute_command_spec_is_rejected_before_popen(self):
        spec = CommandSpec(CommandKind.INTERFACES, ("/bin/echo", "unsafe"), 5)
        with mock.patch("homenettopo.commands.subprocess.Popen") as popen, self.assertRaises(CommandError):
            run_command(spec)
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
