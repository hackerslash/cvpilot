#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pdf_page_count import PageCountError, check_pdf_pages


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def canonical_template(repo: Path) -> Path:
    return repo / "base_template.tex"


def canonical_db(repo: Path) -> Path:
    return repo / "db.json"


def slugify(value: str, *, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def ensure_output_path(repo: Path, output: str | None, *, company: str, role: str) -> Path:
    output_root = (repo / "output").resolve()
    if output:
        candidate = Path(output)
        if not candidate.is_absolute():
            candidate = repo / candidate
        candidate = candidate.resolve()
    else:
        candidate = output_root / f"Resume_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.pdf"

    try:
        candidate.relative_to(output_root)
    except ValueError as exc:
        raise SystemExit(f"Output path must stay under {output_root}") from exc

    return candidate


def emit(payload: dict[str, Any], *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=check,
    )


def current_head(repo: Path) -> str:
    return run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()


def file_contents(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_state(state_file: Path) -> dict[str, Any]:
    return json.loads(file_contents(state_file))


def save_state(state_file: Path, payload: dict[str, Any]) -> None:
    write_text(state_file, json.dumps(payload, indent=2, sort_keys=True))


def source_bundle_text(sources: list[Path]) -> str:
    chunks = []
    for source in sources:
        chunks.append(f"===== SOURCE: {source} =====\n")
        chunks.append(file_contents(source))
        if not chunks[-1].endswith("\n"):
            chunks.append("\n")
        chunks.append("\n")
    return "".join(chunks)


def derive_company_and_role(job_url: str) -> tuple[str, str]:
    parsed = urlparse(job_url)
    host = parsed.netloc.replace("www.", "")
    path_bits = [bit for bit in parsed.path.split("/") if bit]
    company = slugify(host.split(".")[0] if host else "company", fallback="company")
    role = slugify(path_bits[-1] if path_bits else "role", fallback="role")
    return company, role


def build_temp_dir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix, dir="/tmp"))


def remove_dir_if_exists(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # process exists, we just can't signal it


class RefreshLock:
    """PID-based cooperative lock so refresh-base and tailor-job don't race on db.json/base_template.tex."""

    FILENAME = ".refresh-base.lock"

    def __init__(self, repo: Path):
        self.path = repo / self.FILENAME

    def _read(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def is_locked(self) -> bool:
        data = self._read()
        return bool(data and _pid_alive(int(data.get("pid", 0))))

    def acquire(self) -> None:
        data = self._read()
        if data:
            pid = int(data.get("pid", 0))
            if pid and _pid_alive(pid):
                raise SystemExit(
                    f"refresh-base is already running (PID {pid}, started {data.get('acquired_at', '?')}). "
                    f"Wait for it to finish or delete {self.path} if that process is gone."
                )
        self.path.write_text(
            json.dumps({"pid": os.getpid(), "acquired_at": datetime.now().isoformat()}, indent=2),
            encoding="utf-8",
        )

    def release(self) -> None:
        self.path.unlink(missing_ok=True)


@dataclass
class RefreshState:
    command: str
    stage: str
    repo_root: str
    template_path: str
    source_files: list[str]
    source_bundle_path: str
    state_file: str
    review_pdf_path: str | None = None


@dataclass
class TailorState:
    command: str
    stage: str
    repo_root: str
    head_commit: str
    job_url: str
    output_path: str
    branch: str
    worktree: str
    state_file: str
    template_path: str
    db_snapshot_path: str
    company_slug: str
    role_slug: str
    pdf_path: str | None = None


def refresh_prepare(args: argparse.Namespace) -> int:
    repo = repo_root()
    RefreshLock(repo).acquire()
    template = canonical_template(repo)
    missing = [source for source in args.source if not Path(source).exists()]
    if missing:
        raise SystemExit(f"Missing source files: {', '.join(missing)}")

    state_dir = build_temp_dir("resume-refresh-")
    state_file = state_dir / "state.json"
    bundle_path = state_dir / "source-bundle.txt"
    review_pdf = repo / "output" / f"Resume_draft_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    sources = [Path(source).resolve() for source in args.source]
    write_text(bundle_path, source_bundle_text(sources))
    state = RefreshState(
        command="refresh-base",
        stage="prepare",
        repo_root=str(repo),
        template_path=str(template),
        source_files=[str(source) for source in sources],
        source_bundle_path=str(bundle_path),
        state_file=str(state_file),
        review_pdf_path=str(review_pdf),
    )
    save_state(state_file, asdict(state))
    return emit(asdict(state), as_json=args.json)


def refresh_validate(args: argparse.Namespace) -> int:
    repo = repo_root()
    lock = RefreshLock(repo)
    state_file = Path(args.state_file).resolve()
    state = load_state(state_file)
    template = Path(state["template_path"]).resolve()
    if not template.exists():
        raise SystemExit(f"Template not found: {template}")

    compile_dir = build_temp_dir("resume-refresh-build-")
    compile_template = compile_dir / "base_template.tex"
    shutil.copy2(template, compile_template)
    shutil.copy2(repo / "tectonic", compile_dir / "tectonic")

    result = run(["./tectonic", compile_template.name], cwd=compile_dir, check=False)
    output_pdf = Path(state["review_pdf_path"]).resolve()
    payload: dict[str, Any] = {
        "command": "refresh-base",
        "stage": "validate",
        "state_file": str(state_file),
        "template_path": str(template),
        "review_pdf_path": str(output_pdf),
        "compile_dir": str(compile_dir),
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    if result.returncode != 0:
        payload["status"] = "failed"
        lock.release()
        return emit(payload, as_json=args.json)

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(compile_dir / "base_template.pdf", output_pdf)
    payload["status"] = "ok"
    lock.release()
    return emit(payload, as_json=args.json)


def tailor_prepare(args: argparse.Namespace) -> int:
    repo = repo_root()
    template = canonical_template(repo)
    if not template.exists():
        raise SystemExit(f"Canonical template not found: {template}")
    db = canonical_db(repo)
    if not db.exists():
        raise SystemExit(f"Candidate database not found: {db}")
    if RefreshLock(repo).is_locked():
        raise SystemExit(
            "refresh-base is in progress — db.json and base_template.tex may be mid-edit. "
            "Wait for the refresh to complete before tailoring."
        )

    derived_company, derived_role = derive_company_and_role(args.job_url)
    company = slugify(args.company or derived_company, fallback="company")
    role = slugify(args.role or derived_role, fallback="role")
    output_path = ensure_output_path(repo, args.output, company=company, role=role)

    head = current_head(repo)
    branch = f"application/{company}-{timestamp_slug()}"
    worktree = build_temp_dir("tailor-")
    state_file = worktree / ".resume-tailor-state.json"

    branch, result = create_worktree(repo, worktree, head, branch)
    if result.returncode != 0:
        remove_dir_if_exists(worktree)
        payload = {
            "command": "tailor-job",
            "stage": "prepare",
            "status": "failed",
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
        return emit(payload, as_json=args.json)

    worktree_template = worktree / "base_template.tex"
    worktree_db = worktree / "db.json"
    shutil.copy2(template, worktree_template)
    shutil.copy2(db, worktree_db)
    state = TailorState(
        command="tailor-job",
        stage="prepare",
        repo_root=str(repo),
        head_commit=head,
        job_url=args.job_url,
        output_path=str(output_path),
        branch=branch,
        worktree=str(worktree),
        state_file=str(state_file),
        template_path=str(worktree_template),
        db_snapshot_path=str(worktree_db),
        company_slug=company,
        role_slug=role,
    )
    save_state(state_file, asdict(state))
    return emit(asdict(state), as_json=args.json)


def cleanup_worktree(repo: Path, worktree: Path, branch: str) -> None:
    run(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo, check=True)
    run(["git", "branch", "-D", branch], cwd=repo, check=True)


def create_worktree(repo: Path, worktree: Path, head: str, branch: str) -> tuple[str, subprocess.CompletedProcess[str]]:
    result = run(["git", "worktree", "add", "-b", branch, str(worktree), head], cwd=repo, check=False)
    if result.returncode == 0:
        return branch, result

    fallback = branch.replace("/", "-", 1)
    if fallback == branch:
        return branch, result

    retry = run(["git", "worktree", "add", "-b", fallback, str(worktree), head], cwd=repo, check=False)
    if retry.returncode == 0:
        return fallback, retry
    return fallback, retry


def tailor_finalize(args: argparse.Namespace) -> int:
    repo = repo_root()
    state_file = Path(args.state_file).resolve()
    state = load_state(state_file)
    worktree = Path(state["worktree"]).resolve()
    branch = state["branch"]
    template = Path(state["template_path"]).resolve()
    output_pdf = Path(state["output_path"]).resolve()

    payload: dict[str, Any] = {
        "command": "tailor-job",
        "stage": "finalize",
        "state_file": str(state_file),
        "worktree": str(worktree),
        "branch": branch,
        "template_path": str(template),
        "output_path": str(output_pdf),
    }

    if not template.exists():
        payload["status"] = "failed"
        payload["error"] = f"Template not found in worktree: {template}"
        return emit(payload, as_json=args.json)

    result = run(["./tectonic", template.name], cwd=worktree, check=False)
    payload["stdout"] = result.stdout.strip()
    payload["stderr"] = result.stderr.strip()
    if result.returncode != 0:
        payload["status"] = "failed"
        payload["pdf_path"] = None
        return emit(payload, as_json=args.json)

    built_pdf = worktree / f"{template.stem}.pdf"
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built_pdf, output_pdf)
    payload["status"] = "ok"
    payload["pdf_path"] = str(output_pdf)
    try:
        payload.update(check_pdf_pages(output_pdf, max_pages=1))
    except PageCountError as exc:
        payload["page_count"] = None
        payload["page_limit"] = 1
        payload["over_page_limit"] = None
        payload["page_count_error"] = str(exc)

    if payload.get("over_page_limit") is True:
        payload["cleanup"] = "preserved-over-page-limit"
        payload["cleanup_reason"] = "PDF is over the page limit; revise the temporary template and finalize again."
        return emit(payload, as_json=args.json)

    try:
        cleanup_worktree(repo, worktree, branch)
        payload["cleanup"] = "deleted"
    except subprocess.CalledProcessError as exc:
        payload["cleanup"] = "failed"
        payload["cleanup_error"] = exc.stderr.strip() if exc.stderr else str(exc)

    return emit(payload, as_json=args.json)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local resume workflow helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    refresh = subparsers.add_parser("refresh-base", help="Prepare or validate canonical base refresh")
    refresh.add_argument("--stage", choices=["prepare", "validate"], default="prepare")
    refresh.add_argument("--source", action="append", default=[], help="Source file to include")
    refresh.add_argument("--state-file", help="State file emitted by prepare stage")
    refresh.add_argument("--json", action="store_true", help="Emit JSON")

    tailor = subparsers.add_parser("tailor-job", help="Prepare or finalize job-tailored resume rendering")
    tailor.add_argument("--stage", choices=["prepare", "finalize"], default="prepare")
    tailor.add_argument("--job-url", help="Job posting URL")
    tailor.add_argument("--output", help="Output PDF path")
    tailor.add_argument("--company", help="Company slug override")
    tailor.add_argument("--role", help="Role slug override")
    tailor.add_argument("--state-file", help="State file emitted by prepare stage")
    tailor.add_argument("--json", action="store_true", help="Emit JSON")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "refresh-base":
        if args.stage == "prepare":
            if not args.source:
                parser.error("refresh-base --stage prepare requires at least one --source")
            return refresh_prepare(args)
        if not args.state_file:
            parser.error("refresh-base --stage validate requires --state-file")
        return refresh_validate(args)

    if args.stage == "prepare":
        if not args.job_url:
            parser.error("tailor-job --stage prepare requires --job-url")
        return tailor_prepare(args)

    if not args.state_file:
        parser.error("tailor-job --stage finalize requires --state-file")
    return tailor_finalize(args)


if __name__ == "__main__":
    sys.exit(main())
