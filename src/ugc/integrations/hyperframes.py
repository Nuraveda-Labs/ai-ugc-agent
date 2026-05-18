"""HyperFrames CLI wrapper — async subprocess shell-out for `npx hyperframes`.

HyperFrames (github.com/heygen-com/hyperframes) is HeyGen's open-source
HTML→MP4 renderer. We use it as the deterministic composition layer
on top of HeyGen avatar clips.

We don't reimplement any of its logic — this is purely a typed,
async-friendly shell around `npx hyperframes {init,lint,render}` so the
Python pipeline can call into it and surface stderr cleanly on failure.
"""
from __future__ import annotations

import asyncio
import pathlib
import shutil

import structlog

from ugc.config import settings

log = structlog.get_logger(__name__)


class HyperframesError(RuntimeError):
    """Non-zero exit from the hyperframes CLI."""


_HF_CLI_VERSION = "0.4.44"


async def _run(
    args: list[str],
    *,
    cwd: pathlib.Path,
    timeout_s: int = 1800,
) -> tuple[int, str, str]:
    """Run a subprocess; return (rc, stdout, stderr).

    Raises HyperframesError on non-zero rc with stderr in the message.
    """
    s = settings()
    cmd = [s.hyperframes_npx_bin, "--yes", f"hyperframes@{_HF_CLI_VERSION}", *args]
    log.info("hyperframes.run", cmd=cmd, cwd=str(cwd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_s,
        )
    except TimeoutError:
        proc.kill()
        raise HyperframesError(
            f"hyperframes {' '.join(args)} timed out after {timeout_s}s"
        ) from None

    stdout = stdout_b.decode(errors="replace")
    stderr = stderr_b.decode(errors="replace")
    if proc.returncode != 0:
        raise HyperframesError(
            f"hyperframes {' '.join(args)} exit={proc.returncode}\n"
            f"--- stderr ---\n{stderr.strip()[:1500]}\n"
            f"--- stdout ---\n{stdout.strip()[:500]}"
        )
    return proc.returncode or 0, stdout, stderr


def ensure_workdir(workdir: pathlib.Path) -> None:
    """Create the workdir if missing. Caller is responsible for running
    `npx hyperframes init .` inside it once (one-time bootstrap)."""
    workdir.mkdir(parents=True, exist_ok=True)


def npx_available() -> bool:
    s = settings()
    return shutil.which(s.hyperframes_npx_bin) is not None


async def lint(project_dir: pathlib.Path) -> str:
    """`npx hyperframes lint <dir>` — returns stdout on success."""
    rc, out, _err = await _run(
        ["lint", str(project_dir)],
        cwd=project_dir,
    )
    return out


async def render(
    project_dir: pathlib.Path,
    *,
    output_path: pathlib.Path,
    timeout_s: int = 1800,
    extra_args: list[str] | None = None,
) -> pathlib.Path:
    """`npx hyperframes render . --output <abs-out>` from inside project_dir.

    `project_dir` is an HF project (folder with index.html +
    hyperframes.json + meta.json + package.json). We cd into it and use
    `.` so the renderer resolves asset paths (scenes/N.mp4 etc.)
    correctly. `output_path` is forced to absolute to avoid the cwd
    prepending it twice.
    """
    project_dir = project_dir.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    args = ["render", ".", "--output", str(output_path)]
    if extra_args:
        args.extend(extra_args)
    await _run(args, cwd=project_dir, timeout_s=timeout_s)
    if not output_path.exists():
        raise HyperframesError(
            f"hyperframes render returned 0 but {output_path} was not produced"
        )
    return output_path
