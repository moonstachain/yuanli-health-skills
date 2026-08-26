import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_codex_adapter.py"
VALIDATOR = ROOT / "scripts" / "validate_codex_adapter.py"
PUBLIC_SCAN = ROOT / "scripts" / "scan_public_content.py"
QUICK_VALIDATE = Path("/Users/liming/.codex/skills/.system/skill-creator/scripts/quick_validate.py")

SOURCE_IDS = (
    "yuanli.health.kernel.ctx",
    "yuanli.health.kernel.evd",
    "yuanli.health.kernel.dec",
    "yuanli.health.kernel.wpk",
    "yuanli.health.kernel.act",
    "yuanli.health.kernel.out",
    "yuanli.health.kernel.lrn",
    "yuanli.health.experience.first-health-session",
    "yuanli.health.experience.ninety-day-health-experiment",
    "yuanli.health.experience.weekly-health-checkpoint",
    "yuanli.health.experience.doctor-visit-prep",
    "yuanli.health.experience.outcome-review",
    "yuanli.health.experience.learning-reuse",
    "yuanli.health.meta.build",
    "yuanli.health.meta.review",
    "yuanli.health.meta.qualify",
)
PRODUCT_SCHEMA_NAMES = (
    "health-evidence-view-v1",
    "recovery-compass-snapshot-v1",
    "quarter-health-campaign-v1",
    "weekly-experiment-v1",
    "professional-escalation-v1",
)


def run_script(script: Path, *arguments: object, cwd: Path | None = None, env: dict[str, str] | None = None):
    process_env = os.environ.copy()
    process_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        process_env.update(env)
    return subprocess.run(
        [sys.executable, str(script), *(str(item) for item in arguments)],
        cwd=str(cwd or ROOT),
        env=process_env,
        capture_output=True,
        text=True,
        check=False,
    )


def generate(output: Path, *, root: Path = ROOT, metadata: Path | None = None):
    arguments: list[object] = ["--root", root, "--output", output]
    if metadata is not None:
        arguments.extend(("--metadata", metadata))
    result = run_script(GENERATOR, *arguments)
    if result.returncode != 0:
        raise AssertionError(f"generator failed: {result.stdout}\n{result.stderr}")
    return result


def validate(package: Path, *, root: Path = ROOT, metadata: Path | None = None, repository: bool = False):
    arguments: list[object] = ["--root", root, "--package", package]
    if metadata is not None:
        arguments.extend(("--metadata", metadata))
    if repository:
        arguments.append("--check-repository")
    return run_script(VALIDATOR, *arguments)


def regular_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def expected_package_paths() -> set[str]:
    paths = {"SKILL.md", "LICENSE", "NOTICE", "registry-map.json", "SHA256SUMS", "contracts/suite-source-manifest.json"}
    paths.update(f"references/{source_id}.md" for source_id in SOURCE_IDS)
    paths.update(f"contracts/capabilities/{source_id}.json" for source_id in SOURCE_IDS)
    paths.update(f"contracts/qualification-receipts/{source_id}.json" for source_id in SOURCE_IDS)
    paths.update(f"contracts/product-contracts/{schema_name}.schema.json" for schema_name in PRODUCT_SCHEMA_NAMES)
    return paths


def rewrite_checksums(package: Path) -> None:
    lines = []
    for relative, content in sorted(regular_files(package).items()):
        if relative == "SHA256SUMS":
            continue
        lines.append(f"{hashlib.sha256(content).hexdigest()}  {relative}\n")
    (package / "SHA256SUMS").write_text("".join(lines), encoding="utf-8", newline="\n")


def rewrite_metadata_hash(package: Path, metadata: Path) -> None:
    document = json_document(metadata)
    document["package_content_sha256"] = hashlib.sha256((package / "SHA256SUMS").read_bytes()).hexdigest()
    metadata.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")


def copy_repository(destination: Path) -> Path:
    copy = destination / "repository"
    shutil.copytree(
        ROOT,
        copy,
        ignore=shutil.ignore_patterns(".git", "dist", "__pycache__", "*.pyc"),
    )
    return copy


def json_document(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
