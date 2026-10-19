"""Behavioral guards against missing/duplicated CI tests or false-success reports."""
import io
import json
from pathlib import Path
import tempfile
import unittest

from tests.run_ci import (
    RecordedResult, WINDOWS_CASES, fallback_weight, measured_weights, partition,
    required_native_cases, select_cases, unpassed_required, unweighted, verify_reports,
)


class CaseIdentity:
    def __init__(self, identity):
        self.identity = identity

    def id(self):
        return self.identity


class CiSelectionTests(unittest.TestCase):
    def test_new_cases_are_included_once_and_listed_as_unweighted(self):
        cases = [CaseIdentity(name) for name in (
            "heavy.Tests.test_a", "heavy.Tests.test_b", "medium.Tests.test_a",
            "new_module.Tests.test_unanticipated", "small.Tests.test_a",
        )]
        weights = {"heavy.Tests.test_a": 100, "heavy.Tests.test_b": 90,
                   "medium.Tests.test_a": 30, "small.Tests.test_a": 1}
        shards = partition(cases, 3, weights)
        actual = [case.id() for shard in shards for case in shard]
        self.assertCountEqual(actual, [case.id() for case in cases])
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(unweighted(cases, weights), ["new_module.Tests.test_unanticipated"])
        self.assertEqual(fallback_weight(weights), 90)
        self.assertEqual(fallback_weight({}), 1.0)

    def test_slow_independent_cases_split_but_fixture_classes_stay_whole(self):
        class SharedFixture(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                super().setUpClass()

            def test_first(self):
                pass

            def test_second(self):
                pass

        class Independent(unittest.TestCase):
            def test_slow_one(self):
                pass

            def test_slow_two(self):
                pass

        load = unittest.defaultTestLoader.loadTestsFromTestCase
        cases = list(load(SharedFixture)) + list(load(Independent))
        weights = {case.id(): 100 for case in cases}
        shards = [[case.id() for case in shard] for shard in partition(cases, 3, weights)]
        fixture = {case.id() for case in load(SharedFixture)}
        self.assertTrue(any(fixture.issubset(shard) for shard in shards))
        slow = [case.id() for case in load(Independent)]
        self.assertNotEqual(*[next(i for i, s in enumerate(shards) if case in s) for case in slow])
        order = [case.id() for case in cases]
        for shard in shards:
            self.assertEqual(shard, sorted(shard, key=order.index))

    def test_static_and_inherited_class_fixtures_execute_once_per_shard(self):
        events = []
        state = {}

        class StaticFixture(unittest.TestCase):
            @staticmethod
            def setUpClass():
                events.append("setup")
                state["ready"] = True

            @staticmethod
            def tearDownClass():
                events.append("teardown")
                state["ready"] = False

            def test_first(self):
                self.assertTrue(state["ready"])
                events.append("first")

            def test_second(self):
                self.assertTrue(state["ready"])
                events.append("second")

        class InheritedFixture(StaticFixture):
            pass

        for kind in (StaticFixture, InheritedFixture):
            with self.subTest(kind=kind.__name__):
                events.clear()
                cases = list(unittest.defaultTestLoader.loadTestsFromTestCase(kind))
                shards = partition(cases, 2, {case.id(): 1 for case in cases})
                for shard in shards:
                    result = unittest.TextTestRunner(stream=io.StringIO()).run(
                        unittest.TestSuite(shard)
                    )
                    self.assertFalse(result.errors or result.failures)
                self.assertEqual(events, ["setup", "first", "second", "teardown"])
                self.assertFalse(state["ready"])

    def test_weights_come_only_from_one_complete_successful_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            common = {"platform": "windows", "shards": 2, "source_sha": "exact-sha",
                      "successful": True, "scope": ["a", "b"], "run_attempt": 1}
            first = {**common, "shard": 1, "selected": ["a"],
                     "cases": [{"id": "a", "seconds": 1.23456}]}
            second = {**common, "shard": 2, "selected": ["b"],
                      "cases": [{"id": "b", "seconds": 9.0}]}
            (directory / "windows-1.json").write_text(json.dumps(first))
            (directory / "windows-1.inventory.json").write_text(json.dumps({"ignored": True}))
            self.assertRaises((ValueError, FileNotFoundError), measured_weights, directory, "windows")
            retry = directory / "attempt-2"
            retry.mkdir()
            (directory / "windows-2.json").write_text(json.dumps({**second, "successful": False}))
            (retry / "windows-2.json").write_text(json.dumps({**second, "run_attempt": 2}))
            self.assertEqual(measured_weights(directory, "windows"),
                             ("exact-sha", {"a": 1.235, "b": 9.0}))
            for change in ({"source_sha": "other-sha"}, {"successful": False}):
                with self.subTest(change=change):
                    (retry / "windows-2.json").write_text(
                        json.dumps({**second, "run_attempt": 2, **change}))
                    self.assertRaises(ValueError, measured_weights, directory, "windows")
            self.assertRaises(FileNotFoundError, measured_weights, directory, "linux")

    def test_weight_refresh_rejects_ambiguous_mixed_or_unbound_measurements(self):
        for defect in ("ambiguous-attempt", "mixed-shard-counts",
                       "missing-revision", "duplicate-measured-id", "extra-failed-shard",
                       "noncanonical-filename"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                common = {"platform": "windows", "shards": 2,
                          "source_sha": "exact-sha", "successful": True,
                          "scope": ["a", "b"], "run_attempt": 1}
                first = {**common, "shard": 1, "selected": ["a"],
                         "cases": [{"id": "a", "seconds": 1.0}]}
                second = {**common, "shard": 2, "selected": ["b"],
                          "cases": [{"id": "b", "seconds": 2.0}]}
                if defect == "ambiguous-attempt":
                    duplicate = directory / "duplicate"
                    duplicate.mkdir()
                    (duplicate / "windows-1.json").write_text(
                        json.dumps({**first, "successful": False})
                    )
                elif defect == "noncanonical-filename":
                    (directory / "windows-01.json").write_text(
                        json.dumps({**first, "run_attempt": 2, "successful": False})
                    )
                elif defect == "mixed-shard-counts":
                    first.update(shards=1, selected=["a", "b"],
                                 cases=first["cases"] + second["cases"])
                elif defect == "missing-revision":
                    first["source_sha"] = second["source_sha"] = None
                elif defect == "extra-failed-shard":
                    first.update(shards=1, scope=["a"])
                    second["successful"] = False
                else:
                    first["cases"].append({"id": "a", "seconds": 99.0})
                (directory / "windows-1.json").write_text(json.dumps(first))
                (directory / "windows-2.json").write_text(json.dumps(second))
                with self.assertRaises(ValueError):
                    measured_weights(directory, "windows")

    def test_duplicate_identity_is_an_error_not_an_extra_execution(self):
        with self.assertRaisesRegex(ValueError, "Duplicate test identity"):
            partition([CaseIdentity("module.Tests.test_one")] * 2, 2, {})

    def test_windows_overlap_executes_once_and_keeps_native_boundaries(self):
        identities = list(WINDOWS_CASES) + [
            "test_sbtd_upgrade_hosts.ShellResourceTests.test_unicode_resolution_uses_utf8_even_with_legacy_console_encoding",
            "test_install_sh_agent_cli_flow.PowerShellInstallerAgentCliFlowTests.test_powershell_script_has_utf8_bom_for_windows_powershell",
            "test_install_sh_agent_cli_flow.BashInstallerAgentCliFlowTests.test_powershell_unknown_flag",
            "test_install_sh_agent_cli_flow.BashInstallerAgentCliFlowTests.test_bash_only",
            "test_sbtd_graft_entry.SessionRootResolutionTests.test_session_root",
            "test_workflow_contracts.WorkflowContractTests.test_native_ignore",
            "test_sbtd_probe_links.ProbeLinksTests.test_authorized_directory",
        ]
        selected = [case.id() for case in select_cases([CaseIdentity(i) for i in identities], "windows")]
        self.assertCountEqual(selected, [i for i in identities if not i.endswith("test_bash_only")])
        self.assertEqual(len(selected), len(set(selected)))

    def test_missing_required_windows_case_blocks_selection(self):
        with self.assertRaisesRegex(ValueError, "Required Windows cases missing"):
            select_cases([CaseIdentity(i) for i in WINDOWS_CASES[1:]], "windows")

    def test_class_setup_failure_cannot_be_reported_as_success(self):
        class BrokenSetup(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError("fixture setup failed")

            def test_not_reached(self):
                self.fail("setup should prevent this")

        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=RecordedResult).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(BrokenSetup)
        )
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.errors), 1)
        self.assertIn("fixture setup failed", result.errors[0][1])

    def test_aggregate_requires_complete_disjoint_same_revision_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            first = {
                "platform": "linux", "shard": 1, "shards": 2, "source_sha": "exact-sha",
                "successful": True, "scope": ["a", "b"], "selected": ["a"], "run_attempt": 1,
            }
            second = {**first, "shard": 2, "selected": ["b"]}
            (directory / "linux-1.json").write_text(json.dumps(first))
            path = directory / "linux-2.json"
            with self.assertRaises(FileNotFoundError):
                verify_reports(directory, "linux", 2, "exact-sha")
            path.write_text(json.dumps(second))
            self.assertEqual(verify_reports(directory, "linux", 2, "exact-sha"), 2)
            for change in (
                {"selected": ["a"]}, {"selected": []}, {"selected": ["outside"]},
                {"scope": ["a", "b", "missing"]}, {"source_sha": "old-sha"},
                {"successful": False}, {"shard": 1}, {"shards": 3},
            ):
                with self.subTest(change=change):
                    path.write_text(json.dumps({**second, **change}))
                    with self.assertRaises(ValueError):
                        verify_reports(directory, "linux", 2, "exact-sha")

    def test_partial_retry_retains_successful_shard_and_replaces_failed_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            initial = directory / "attempt-1"
            retry = directory / "attempt-2"
            initial.mkdir()
            retry.mkdir()
            common = {
                "platform": "linux", "shards": 2, "source_sha": "exact-sha",
                "scope": ["a", "b"], "run_attempt": 1, "successful": True,
            }
            (initial / "linux-1.json").write_text(json.dumps({**common, "shard": 1, "selected": ["a"]}))
            failed = {**common, "shard": 2, "selected": ["b"], "successful": False}
            (initial / "linux-2.json").write_text(json.dumps(failed))
            with self.assertRaises(ValueError):
                verify_reports(directory, "linux", 2, "exact-sha")
            repaired = {**failed, "run_attempt": 2, "successful": True}
            (retry / "linux-2.json").write_text(json.dumps(repaired))
            self.assertEqual(verify_reports(directory, "linux", 2, "exact-sha"), 2)
            # A newer failure must not be hidden by falling back to an older pass.
            failed_retry = {**common, "shard": 1, "selected": ["a"], "run_attempt": 2, "successful": False}
            (retry / "linux-1.json").write_text(json.dumps(failed_retry))
            with self.assertRaises(ValueError):
                verify_reports(directory, "linux", 2, "exact-sha")

    def test_required_native_skip_or_expected_failure_does_not_count_as_pass(self):
        executed = []
        class NativeChecks(unittest.TestCase):
            def test_skipped(self):
                self.skipTest("native capability unavailable")

            @unittest.expectedFailure
            def test_expected_failure(self):
                self.fail("known native failure")

            def test_passed(self):
                executed.append(self.id())

        cases = list(unittest.defaultTestLoader.loadTestsFromTestCase(NativeChecks))
        required = {case.id() for case in cases}
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=RecordedResult).run(
            unittest.TestSuite(cases)
        )
        self.assertTrue(result.wasSuccessful())  # unittest alone accepts skip/xfail.
        self.assertCountEqual(
            unpassed_required(required, result.records),
            required - set(executed),
        )

    def test_native_requirements_keep_platform_specific_failures_distinct(self):
        powershell = "test_install_sh_agent_cli_flow.BashInstallerAgentCliFlowTests.test_powershell_new_case"
        sensitive = "test_sbtd_upgrade_inventory.PhysicalTargetPlanTests.test_case_sensitive_onboard_provider_uses_selected_installation"
        windows = required_native_cases("windows", [powershell])
        linux = required_native_cases("linux", [powershell])
        self.assertIn(sensitive, windows)  # The fixture enables NTFS per-directory sensitivity.
        self.assertIn(sensitive, linux)
        self.assertTrue(set(WINDOWS_CASES).issubset(windows))
        records = [
            {"id": identity, "status": "skipped" if identity == powershell else "passed"}
            for identity in windows | linux
        ]
        self.assertEqual(unpassed_required(windows, records), [powershell])
        self.assertEqual(unpassed_required(linux, records), [])
        self.assertEqual(unpassed_required(required_native_cases("macos", [powershell]), records), [])
