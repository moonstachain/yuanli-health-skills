import contextlib
import io
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests._adapter_support import GENERATOR, ROOT, VALIDATOR, copy_repository, generate


@contextlib.contextmanager
def _real_temporary_directory():
    with tempfile.TemporaryDirectory(dir=Path(os.path.realpath(tempfile.gettempdir()))) as directory:
        yield Path(directory)


@contextlib.contextmanager
def _script_namespace(script: Path, run_name: str):
    sys.path.insert(0, str(script.parent))
    try:
        yield runpy.run_path(str(script), run_name=run_name)
    finally:
        sys.path.remove(str(script.parent))


def _call_main(main, arguments: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return main(arguments)


def _descriptor_count() -> int:
    for directory in (Path("/dev/fd"), Path("/proc/self/fd")):
        if directory.is_dir():
            return len(os.listdir(directory))
    raise unittest.SkipTest("platform does not expose a process descriptor directory")


class Task0MetadataAnchoringTests(unittest.TestCase):
    def test_generator_keeps_metadata_write_in_original_anchored_parent(self):
        with _real_temporary_directory() as temporary:
            repository = copy_repository(temporary / "source")
            safe_anchor = temporary / "safe-anchor"
            safe_anchor.mkdir()
            safe_package = safe_anchor / "package"
            metadata = safe_anchor / "release-metadata.json"
            attacker_anchor = temporary / "attacker-anchor"
            attacker_anchor.mkdir()
            attacker_metadata = attacker_anchor / metadata.name
            attacker_metadata.write_bytes(b"attacker metadata must not change\n")
            before = attacker_metadata.read_bytes()
            parked_anchor = temporary / "parked-safe-anchor"

            with _script_namespace(GENERATOR, "task0_metadata_generator") as namespace:
                main = namespace["main"]
                original_write = main.__globals__["_write_package"]

                def write_then_substitute(output, files):
                    original_write(output, files)
                    safe_anchor.rename(parked_anchor)
                    safe_anchor.symlink_to(attacker_anchor, target_is_directory=True)

                main.__globals__["_write_package"] = write_then_substitute
                result = _call_main(
                    main,
                    ["--root", str(repository), "--output", str(safe_package), "--metadata", str(metadata)],
                )

            self.assertEqual(result, 0)
            self.assertEqual(attacker_metadata.read_bytes(), before)
            self.assertTrue((parked_anchor / metadata.name).is_file())

    def test_validator_reads_metadata_from_original_anchored_parent(self):
        with _real_temporary_directory() as temporary:
            repository = copy_repository(temporary / "source")
            safe_anchor = temporary / "safe-anchor"
            safe_anchor.mkdir()
            safe_package = safe_anchor / "package"
            metadata = safe_anchor / "release-metadata.json"
            generate(safe_package, root=repository, metadata=metadata)
            attacker_anchor = temporary / "attacker-anchor"
            attacker_anchor.mkdir()
            attacker_metadata = attacker_anchor / metadata.name
            attacker_metadata.write_bytes(b"attacker metadata must remain unread\n")
            before = attacker_metadata.read_bytes()
            parked_anchor = temporary / "parked-safe-anchor"

            with _script_namespace(VALIDATOR, "task0_metadata_validator") as namespace:
                main = namespace["main"]
                original_validate = main.__globals__["validate_package"]

                def validate_then_substitute(root, package):
                    result = original_validate(root, package)
                    safe_anchor.rename(parked_anchor)
                    safe_anchor.symlink_to(attacker_anchor, target_is_directory=True)
                    return result

                main.__globals__["validate_package"] = validate_then_substitute
                result = _call_main(
                    main,
                    ["--root", str(repository), "--package", str(safe_package), "--metadata", str(metadata)],
                )

            self.assertEqual(result, 0)
            self.assertEqual(attacker_metadata.read_bytes(), before)


class Task0SnapshotStabilityTests(unittest.TestCase):
    def _snapshot_with_interruption(self, interrupt):
        guard = ROOT / "scripts" / "lexical_path_guard.py"
        with _real_temporary_directory() as temporary, _script_namespace(guard, "task0_snapshot") as namespace:
            package = temporary / "package"
            package.mkdir()
            target = package / "payload.txt"
            target.write_bytes(b"a" * 4096)
            original_read = namespace["os"].read
            interrupted = False

            def read_then_interrupt(descriptor, size):
                nonlocal interrupted
                result = original_read(descriptor, size)
                if result and not interrupted:
                    interrupted = True
                    interrupt(target, package)
                return result

            with namespace["inspect_lexical_path"](package) as identity, mock.patch.object(
                namespace["os"], "read", side_effect=read_then_interrupt
            ):
                with self.assertRaisesRegex(ValueError, "package tree changed"):
                    identity.snapshot()
            self.assertTrue(interrupted)

    def test_snapshot_rejects_same_size_mutation_during_read(self):
        self._snapshot_with_interruption(lambda target, _package: target.write_bytes(b"b" * 4096))

    def test_snapshot_rejects_hardlink_added_during_read(self):
        self._snapshot_with_interruption(lambda target, package: os.link(target, package / "late-hardlink.txt"))


class Task0MetadataWriteStabilityTests(unittest.TestCase):
    def test_metadata_replacement_does_not_modify_an_old_inode_hardlinked_during_write(self):
        guard = ROOT / "scripts" / "lexical_path_guard.py"
        with _real_temporary_directory() as temporary, _script_namespace(guard, "task0_metadata_write") as namespace:
            parent = temporary / "metadata-parent"
            parent.mkdir()
            metadata = parent / "release-metadata.json"
            metadata.write_bytes(b"old metadata\n")
            external = temporary / "external-hardlink.json"
            original_write = namespace["os"].write
            linked = False

            def link_then_write(descriptor, content):
                nonlocal linked
                if not linked:
                    os.link(metadata, external)
                    linked = True
                return original_write(descriptor, content)

            with namespace["inspect_lexical_path"](parent) as identity, mock.patch.object(
                namespace["os"], "write", side_effect=link_then_write
            ):
                try:
                    identity.write_regular_file(metadata.name, b"new metadata\n")
                except ValueError:
                    pass
            self.assertTrue(linked)
            self.assertEqual(external.read_bytes(), b"old metadata\n")
            self.assertEqual(metadata.read_bytes(), b"new metadata\n")


class Task0InventoryAndOwnershipTests(unittest.TestCase):
    def test_clear_rejects_width_over_the_shared_entry_budget_before_deleting(self):
        guard = ROOT / "scripts" / "lexical_path_guard.py"
        with _real_temporary_directory() as temporary, _script_namespace(guard, "task0_clear_budget") as namespace:
            package = temporary / "package"
            package.mkdir()
            for name in ("one", "two", "three"):
                (package / name).write_text(name, encoding="utf-8")
            namespace["_EntryBudget"].consume.__globals__["_MAX_TREE_ENTRIES"] = 2
            with namespace["inspect_lexical_path"](package) as identity:
                with self.assertRaisesRegex(ValueError, "safety budget"):
                    identity.clear_contents()
            self.assertEqual({path.name for path in package.iterdir()}, {"one", "two", "three"})

    def test_snapshot_uses_a_bounded_incremental_directory_enumerator(self):
        guard = ROOT / "scripts" / "lexical_path_guard.py"
        with _real_temporary_directory() as temporary, _script_namespace(guard, "task0_scandir") as namespace:
            package = temporary / "package"
            package.mkdir()
            (package / "payload.txt").write_text("payload", encoding="utf-8")
            with namespace["inspect_lexical_path"](package) as identity, mock.patch.object(
                namespace["os"], "listdir", side_effect=AssertionError("unbounded listdir forbidden")
            ):
                files, issues = identity.snapshot()
            self.assertEqual(files, {"payload.txt": b"payload"})
            self.assertEqual(issues, [])

    def test_inspect_closes_child_descriptor_when_fstat_fails_before_handoff(self):
        guard = ROOT / "scripts" / "lexical_path_guard.py"
        with _real_temporary_directory() as temporary, _script_namespace(guard, "task0_inspect_fstat") as namespace:
            target = temporary / "target"
            target.mkdir()
            baseline = _descriptor_count()
            with mock.patch.object(namespace["os"], "fstat", side_effect=OSError("injected fstat failure")):
                with self.assertRaisesRegex(OSError, "injected fstat failure"):
                    namespace["inspect_lexical_path"](target)
            self.assertEqual(_descriptor_count(), baseline)

    def test_create_root_closes_child_descriptor_when_fstat_fails_before_handoff(self):
        guard = ROOT / "scripts" / "lexical_path_guard.py"
        with _real_temporary_directory() as temporary, _script_namespace(guard, "task0_create_fstat") as namespace:
            target = temporary / "missing" / "package"
            baseline = _descriptor_count()
            with namespace["inspect_lexical_path"](target) as identity:
                with mock.patch.object(namespace["os"], "fstat", side_effect=OSError("injected fstat failure")):
                    with self.assertRaisesRegex(ValueError, "package root"):
                        identity.write_files({"payload.txt": b"payload"})
            self.assertEqual(_descriptor_count(), baseline)

    def test_generator_and_validator_close_descriptors_in_the_calling_process(self):
        with _real_temporary_directory() as temporary:
            repository = copy_repository(temporary / "source")
            package = temporary / "package"
            generate(package, root=repository)
            package_link = temporary / "package-link"
            package_link.symlink_to(package, target_is_directory=True)
            baseline = _descriptor_count()
            with _script_namespace(GENERATOR, "task0_generator_in_process") as generator, _script_namespace(
                VALIDATOR, "task0_validator_in_process"
            ) as validator:
                for _ in range(4):
                    self.assertEqual(
                        _call_main(generator["main"], ["--root", str(repository), "--output", str(package)]),
                        0,
                    )
                    self.assertNotEqual(
                        _call_main(validator["main"], ["--root", str(repository), "--package", str(package_link)]),
                        0,
                    )
            self.assertEqual(_descriptor_count(), baseline)


class Task0ScannerStateTests(unittest.TestCase):
    @staticmethod
    def _finding_classes():
        return runpy.run_path(str(ROOT / "scripts" / "scan_public_content.py"), run_name="task0_scanner")["finding_classes"]

    def test_ambiguous_concatenated_quote_continuation_keeps_sensitive_relation_pending(self):
        content = (
            "template = unknownPrefix_9'ordinary first physical line\n"
            "SubjectIdentifier: {placeholder}\n"
            "' + unknownPrefix_9'raw: opaque-identifier'\n"
        ).encode("utf-8")
        self.assertIn("patient_identifier", self._finding_classes()("probe.txt", content))

    def test_contraction_does_not_carry_ambiguous_quote_state_to_unrelated_placeholder(self):
        content = b"don't carry scanner state into unrelated prose\nSubjectIdentifier: {placeholder}\n"
        self.assertEqual(self._finding_classes()("ordinary.txt", content), ())


class Task0PlatformContractTests(unittest.TestCase):
    def test_guard_rejects_unsupported_platform_with_a_stable_capability_message(self):
        guard = ROOT / "scripts" / "lexical_path_guard.py"
        with _real_temporary_directory() as temporary, _script_namespace(guard, "task0_platform") as namespace:
            with mock.patch.object(namespace["os"], "name", "nt"):
                with self.assertRaisesRegex(ValueError, "POSIX descriptor capabilities required"):
                    namespace["inspect_lexical_path"](temporary / "package")


if __name__ == "__main__":
    unittest.main()
