"""THE ONE LOCK EVERY GIT WRITER ON THIS BOX TAKES -- the Python half.

WHAT THIS IS FOR, MEASURED 2026-09-23. The trading box's hourly adoption
(`desks/mt5/scripts/Adopt-And-Seal.ps1`) had ended at

    Adopt-Release exited 1 -- partial adoption; NOT sealing a tree that only half-matches
    the branch

every hour it ran, and one hand run showed the texture underneath it:

    chunk add failed; retrying 2 path(s) individually
    skipped 2 pathspec(s) that match nothing on disk or in the index
    fatal: Unable to create 'C:/opt/quant/.git/index.lock': File exists.

A foreign writer held the index between this adoption's `git add` and its `git commit`.
Four PowerShell writers -- adopt-and-seal, seal-if-clean, intel-ship-adopt and
shadow-sync -- already serialise on the named mutex `GitWriterMutex.ps1` creates. NOTHING
IN PYTHON DID, and Python is most of what runs on this box: the daily forensic snapshot
(`scripts/git_snapshot.py`, a repository-wide `git add -A`), the document replay healer
(`scripts/check_doc_replay_fence.py`, `git checkout HEAD -- <path>`), the unit-health
publisher and the release arm both write the index too. Each one is a `.git/index.lock`
the adoption can lose to, and losing it is four days of unshipped fixes.

So this module is the same lock, reachable from Python, plus the two things the
PowerShell side learned the hard way:

  * A LOCK THAT CANNOT BE OPENED IS NOT A LOCK SOMEBODY ELSE HOLDS. A named mutex created
    under one principal with its default security descriptor cannot be opened by the next
    principal at all, and for four days that refusal was reported as contention that had
    never been measured. Every acquisition here reports `held`, `mechanism` and `why`
    separately, and a lock that could not be examined degrades to the FILE mechanism
    rather than pretending either answer.

  * A STALE `index.lock` IS REMOVABLE, AND ONLY WITH THE FACT RECORDED. git leaves the
    file behind when a writer is killed (a task limit, a reboot, an OOM). Removing it
    while a live git process holds it corrupts an index; refusing forever wedges the box.
    `clear_stale_index_lock` removes it only when no git process is alive AND the file has
    not been touched for `stale_s`, and it returns what it did so the caller can publish
    it instead of swallowing it.

USE IT LIKE THIS::

    from libs.ops import git_writer_lock as gwl

    with gwl.git_writer_lock(repo) as lock:
        if not lock.held:
            print(f"not writing the index: {lock.why}")
            return
        gwl.run_git(repo, ["add", "--", path])

`run_git` retries the index under the lock with a bounded backoff, because holding the
mutex does not stop a writer running OLD code, and the box always has some.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: The lock the PowerShell writers take. Kept in step with
#: `desks/mt5/scripts/GitWriterMutex.ps1`; a test fails when the two drift apart.
#: `Global\` first so a writer in another session (a scheduled task runs in session 0, an
#: RDP console does not) is coordinated with; `Local\` where the Global namespace is
#: refused.
MUTEX_NAMES: tuple[str, ...] = ("Global\\MT5-GitWriter-v2", "Local\\MT5-GitWriter-v2")

#: The pre-2026-09-23 name. Taken BEST EFFORT so a writer still running the old code is
#: still coordinated with while it lasts; a name that cannot be opened is a note, never a
#: refusal -- that confusion is exactly what wedged this box for four days.
LEGACY_MUTEX_NAME = "Local\\MT5-GitWriter"

#: Nine minutes, the same wait `Adopt-And-Seal.ps1` uses: the shadow sync's own limit is
#: ten, so a writer that has not finished in nine is not merely slow.
DEFAULT_TIMEOUT_S = 540.0

#: An `index.lock` younger than this may still belong to a writer between two of its own
#: git calls. Older than this, with no git process alive, it is debris.
DEFAULT_STALE_S = 120.0

_SDDL_EVERYONE = "D:(A;;GA;;;WD)"
_WAIT_OBJECT_0 = 0x00000000
_WAIT_ABANDONED = 0x00000080
_WAIT_TIMEOUT = 0x00000102
_SYNCHRONIZE = 0x00100000
_MUTEX_MODIFY_STATE = 0x0001


def _jitter_s() -> float:
    """De-synchronise two writers' retries WITHOUT a random number generator.

    Two processes that back off on the same schedule collide on every attempt, so the
    backoff needs a per-process offset. It does not need entropy, and reaching for an RNG
    here would be a security-flagged import for a scheduling detail: the pid is already
    distinct per writer and stable within one, which is exactly the property wanted.
    """
    return (os.getpid() % 7) / 10.0


@dataclass
class LockHandle:
    """What an acquisition actually got, with the reason separated from the outcome."""

    held: bool
    mechanism: str  # "mutex" | "file" | "none"
    name: str
    why: str = ""
    waited_s: float = 0.0
    abandoned: bool = False
    notes: list[str] = field(default_factory=list)
    _handles: list[Any] = field(default_factory=list, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {"held": self.held, "mechanism": self.mechanism, "name": self.name,
                "why": self.why, "waited_s": round(self.waited_s, 3),
                "abandoned": self.abandoned, "notes": list(self.notes)}


# --------------------------------------------------------------- the Windows named mutex
def _win_api() -> Any:
    """kernel32/advapi32, or None where there is no Windows to ask."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

        class SECURITY_ATTRIBUTES(ctypes.Structure):  # Win32 name, kept verbatim
            _fields_ = (("nLength", wintypes.DWORD),
                        ("lpSecurityDescriptor", ctypes.c_void_p),
                        ("bInheritHandle", wintypes.BOOL))

        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.OpenMutexW.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        return {"ctypes": ctypes, "kernel32": kernel32, "advapi32": advapi32,
                "SA": SECURITY_ATTRIBUTES}
    except Exception:  # pragma: no cover -- a Windows without ctypes is not a case here
        return None


def _permissive_sa(api: Any) -> Any:
    """A SECURITY_ATTRIBUTES every principal on this box can open.

    The whole four-day outage was a mutex whose creator's default descriptor locked every
    other principal out. This is a synchronisation NAME on one machine, not a secret: the
    only thing another local process can do with it is wait, which is what every
    legitimate writer already does.
    """
    ctypes = api["ctypes"]
    psd = ctypes.c_void_p()
    ok = api["advapi32"].ConvertStringSecurityDescriptorToSecurityDescriptorW(
        _SDDL_EVERYONE, 1, ctypes.byref(psd), None)
    if not ok:
        return None
    sa = api["SA"]()
    sa.nLength = ctypes.sizeof(sa)
    sa.lpSecurityDescriptor = psd
    sa.bInheritHandle = False
    return sa


def _open_one_mutex(api: Any, name: str) -> tuple[Any, str]:
    """(handle, why). A handle OR a reason, never a silent None."""
    ctypes = api["ctypes"]
    sa = _permissive_sa(api)
    handle = api["kernel32"].CreateMutexW(ctypes.byref(sa) if sa is not None else None,
                                          False, name)
    if handle:
        return handle, ""
    why = f"create({name}): WinError {ctypes.get_last_error()}"
    for rights in (_SYNCHRONIZE | _MUTEX_MODIFY_STATE, _SYNCHRONIZE):
        handle = api["kernel32"].OpenMutexW(rights, False, name)
        if handle:
            return handle, ""
        why += f" | open({rights:#x}): WinError {ctypes.get_last_error()}"
    return None, why


def _acquire_mutex(timeout_s: float, names: Sequence[str] = MUTEX_NAMES,
                   legacy: str | None = LEGACY_MUTEX_NAME) -> LockHandle | None:
    """The mutex acquisition, or None where there is no mutex to take at all."""
    api = _win_api()
    if api is None:
        return None
    why = ""
    for name in names:
        handle, one_why = _open_one_mutex(api, name)
        if not handle:
            why = (why + " " + one_why).strip()
            continue
        t0 = time.monotonic()
        rc = api["kernel32"].WaitForSingleObject(handle, int(max(0.0, timeout_s) * 1000))
        waited = time.monotonic() - t0
        if rc not in (_WAIT_OBJECT_0, _WAIT_ABANDONED):
            api["kernel32"].CloseHandle(handle)
            reason = ("another git writer held it for the full wait"
                      if rc == _WAIT_TIMEOUT else f"WaitForSingleObject rc={rc:#x}")
            return LockHandle(held=False, mechanism="mutex", name=name, why=reason,
                              waited_s=waited)
        lock = LockHandle(held=True, mechanism="mutex", name=name, waited_s=waited,
                          abandoned=rc == _WAIT_ABANDONED)
        lock._handles.append((api, handle))
        if rc == _WAIT_ABANDONED:
            # A writer that died holding it. That is a GRANT, not a wedge -- and it is
            # said out loud, because a writer killed mid-index is exactly when a stale
            # index.lock gets left behind.
            lock.notes.append(f"{name} was abandoned by a writer that died holding it")
        if legacy:
            l_handle, l_why = _open_one_mutex(api, legacy)
            if l_handle:
                l_rc = api["kernel32"].WaitForSingleObject(
                    l_handle, int(min(30.0, max(0.0, timeout_s)) * 1000))
                if l_rc in (_WAIT_OBJECT_0, _WAIT_ABANDONED):
                    lock._handles.append((api, l_handle))
                else:
                    api["kernel32"].CloseHandle(l_handle)
                    lock.notes.append(f"legacy {legacy} held by another writer; "
                                      f"proceeding on {name}")
            else:
                lock.notes.append(f"legacy {legacy} not openable ({l_why}); "
                                  "a note, not a refusal")
        return lock
    return LockHandle(held=False, mechanism="none", name=",".join(names),
                      why=why or "no mutex name could be opened")


def _release_mutex(lock: LockHandle) -> None:
    for api, handle in reversed(lock._handles):
        try:
            api["kernel32"].ReleaseMutex(handle)
        finally:
            api["kernel32"].CloseHandle(handle)
    lock._handles.clear()


# ------------------------------------------------------------ the portable file fallback
def _lock_path(repo: Path) -> Path:
    return repo / ".git" / "quant-git-writer.lock"


def _acquire_file(repo: Path, timeout_s: float, stale_s: float) -> LockHandle:
    """O_EXCL lock file, with takeover of one a dead process left behind.

    The mechanism the VPS and every test uses, and the one the box falls back to when the
    mutex namespace is refused. A lock file whose owner is gone is debris for exactly the
    same reason an `index.lock` is, and is taken over with the fact recorded.
    """
    path = _lock_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.0, timeout_s)
    notes: list[str] = []
    t0 = time.monotonic()
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(f"{os.getpid()} {time.time():.3f}\n")
            return LockHandle(held=True, mechanism="file", name=str(path),
                              waited_s=time.monotonic() - t0, notes=notes,
                              _path=path)
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            continue
        if age > stale_s and not _pid_alive(_lock_pid(path)):
            try:
                path.unlink()
            except OSError:
                pass
            else:
                notes.append(f"took over a lock file {age:.0f}s old whose owner is gone")
                continue
        if time.monotonic() >= deadline:
            return LockHandle(held=False, mechanism="file", name=str(path),
                              why=f"another writer held {path.name} for the full wait",
                              waited_s=time.monotonic() - t0, notes=notes)
        time.sleep(min(2.0, 0.25 + _jitter_s()))


def _lock_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _pid_alive(pid: int | None) -> bool:
    # `<= 0` FIRST: on Windows `tasklist /fi "pid eq 0"` reports the System Idle Process, so a
    # lock file whose owner field is 0 or garbage would read as held forever by a process that
    # is not a writer and cannot be one.
    if pid is None or pid <= 0:
        return False
    if sys.platform == "win32":
        rc, out = _run(["tasklist", "/fi", f"pid eq {pid}", "/nh"], timeout=20)
        return rc == 0 and str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# ----------------------------------------------------------------------- the public lock
@contextmanager
def git_writer_lock(repo: Path | str | None = None, *,
                    timeout_s: float = DEFAULT_TIMEOUT_S,
                    stale_s: float = DEFAULT_STALE_S,
                    mechanism: str = "auto") -> Iterator[LockHandle]:
    """Hold the desk's git-writer lock for the body, then release it.

    `mechanism` is "auto" (mutex where one can be taken, file otherwise), "file" (the
    portable path, which is what the tests exercise) or "mutex".

    THE BODY ALWAYS RUNS. A governance fault must not stop the desk (L1.37) and a lock
    that could not be examined is not evidence of contention -- so the caller is told
    `held` and `why` and decides. Every caller in this repo declines to write when
    `held` is false; that decision is theirs to make with the reason in hand.
    """
    root = Path(repo) if repo is not None else _repo_root()
    lock: LockHandle | None = None
    if mechanism in ("auto", "mutex"):
        lock = _acquire_mutex(timeout_s)
        if lock is not None and not lock.held and lock.mechanism == "none" \
                and mechanism == "auto":
            why = lock.why
            lock = _acquire_file(root, timeout_s, stale_s)
            lock.notes.append(f"no mutex name could be opened ({why}); used the lock file")
    if lock is None:
        lock = _acquire_file(root, timeout_s, stale_s)
    try:
        yield lock
    finally:
        if lock.held:
            if lock.mechanism == "mutex":
                _release_mutex(lock)
            elif lock._path is not None:
                with contextlib.suppress(OSError):
                    lock._path.unlink()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- the index.lock itself
def _run(argv: Sequence[str], timeout: float = 120.0,
         cwd: Path | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout,
                           cwd=str(cwd) if cwd else None, check=False, errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def git_processes_alive() -> bool:
    """Is any git process running on this machine right now?

    Deliberately machine-wide and deliberately coarse. The question a stale-lock decision
    needs is "could anything still be mid-index", and a git in another checkout answers it
    the same way as far as the cost of being wrong goes: we wait one more round.
    """
    if sys.platform == "win32":
        rc, out = _run(["tasklist", "/fi", "imagename eq git.exe", "/nh"], timeout=30)
        return rc == 0 and "git.exe" in out.lower()
    rc, out = _run(["pgrep", "-x", "git"], timeout=30)
    return rc == 0 and bool(out.strip())


def clear_stale_index_lock(repo: Path | str, *, stale_s: float = DEFAULT_STALE_S,
                           alive: Any = None) -> dict[str, Any]:
    """Remove `.git/index.lock` ONLY when it is debris, and say what was done.

    Returns a record every time -- `{"present": bool, "removed": bool, "why": str,
    "age_s": float|None}` -- because "there was no lock" and "there was one and it was
    somebody's" must never render identically (L1.28a).
    """
    root = Path(repo)
    lock = root / ".git" / "index.lock"
    rec: dict[str, Any] = {"present": False, "removed": False, "age_s": None, "why": ""}
    try:
        age = time.time() - lock.stat().st_mtime
    except OSError:
        rec["why"] = "no index.lock"
        return rec
    rec["present"] = True
    rec["age_s"] = round(age, 1)
    if age <= stale_s:
        rec["why"] = (f"index.lock is {age:.0f}s old (<= {stale_s:.0f}s): a live writer "
                      "between two of its own git calls looks exactly like this")
        return rec
    is_alive = (alive or git_processes_alive)()
    if is_alive:
        rec["why"] = (f"index.lock is {age:.0f}s old but a git process is running; "
                      "removing it could corrupt that writer's index")
        return rec
    try:
        lock.unlink()
    except OSError as exc:
        rec["why"] = f"index.lock is debris but could not be removed: {exc}"
        return rec
    rec["removed"] = True
    rec["why"] = (f"removed a stale index.lock {age:.0f}s old with no git process alive "
                  "-- debris from a writer that was killed mid-index")
    return rec


def run_git(repo: Path | str, args: Sequence[str], *, timeout: float = 300.0,
            attempts: int = 5, stale_s: float = DEFAULT_STALE_S,
            sleep: Any = time.sleep) -> tuple[int, str, list[str]]:
    """`git -C <repo> <args>`, retried with bounded backoff when the index is contended.

    Returns (rc, output, notes). HOLDING THE MUTEX IS NOT ENOUGH ON THIS BOX: a writer
    running code from before the lock existed, an operator's shell, or a hook can still be
    between its own `add` and `commit`. The retry is what makes the adoption survive that
    instead of exiting 1 on it. The backoff is bounded because a contended index that
    never clears is a DEFECT to publish, not a loop to sit in.
    """
    root = Path(repo)
    notes: list[str] = []
    delay = 1.0
    rc, out = 127, ""
    for attempt in range(1, max(1, attempts) + 1):
        rc, out = _run(["git", "-C", str(root), *args], timeout=timeout)
        if rc == 0 or "index.lock" not in out:
            return rc, out, notes
        notes.append(f"attempt {attempt}: git {' '.join(args[:2])} lost the index lock")
        cleared = clear_stale_index_lock(root, stale_s=stale_s)
        if cleared["present"]:
            notes.append(str(cleared["why"]))
        if attempt >= max(1, attempts):
            break
        sleep(delay + _jitter_s())
        delay = min(delay * 2, 30.0)
    return rc, out, notes


# ------------------------------------------------------------------ reaping a hung writer
#
# THE HALF THAT WAS MISSING, MEASURED 2026-09-24 01:10Z ON THE TRADING BOX.
#
# Four git processes had been alive since 2026-09-23 22:03:53Z:
#
#     git -C C:\opt\quant -c merge.autoStash=false merge -s ours d97d2d592a9f ...
#     git stash create
#     git update-index --ignore-skip-worktree-entries -z --add --remove --stdin
#
# `git update-index --stdin` was blocked on a pipe that nobody was ever going to write to, so
# `git stash create` never returned, so the release merge never returned. Over a 20 s window all
# four moved 0.000 s of CPU and 0 bytes of I/O: not slow, STOPPED. They held `.git/index.lock`
# and the `MT5-GitWriter` mutex, and because of that:
#
#   * `Adopt-And-Seal.ps1` logged "another git writer held Local\MT5-GitWriter for the full
#     9 min; not adopting under it" at 22:41, 22:53 and 23:00 and shipped nothing;
#   * `MT5-IntelShip`, `MT5-ShadowSync` and `MT5-SealIfClean` serialise on the same object and
#     refused too;
#   * the box sat 7 commits behind origin running code that was not the shipped code.
#
# The desk already SAW this. `scripts/check_scheduled_tasks.py::stuck_writers` names the pids and
# says in its own text that "a hung ssh from 2026-09-12 held it for THREE DAYS and refused every
# adopt" -- and then nothing kills them. Detection with no reaper is III.16's defect exactly: an
# organ that reports forever and changes nothing.
#
# `clear_stale_index_lock` above cannot cover this either, and deliberately so: it refuses while
# ANY git process is alive, machine-wide. That guard is right for a quiet machine. THIS MACHINE IS
# NEVER QUIET -- the intelligence shipper runs `git status --porcelain` continuously, so
# `git_processes_alive()` is true essentially always and the stale-lock path can never fire here.
# The fix is not to weaken that guard. It is to remove the hung writer FIRST, so that afterwards
# the remaining git processes are real ones and the existing guard means what it says.
#
# WHAT THIS WILL AND WILL NOT KILL. A process is reaped only when all four hold:
#   1. it is a `git` or `ssh` executable -- never `sshd` (the SSH SERVER is long-lived by design,
#      and matching it once reported a healthy 3.9-day-old service as a stuck writer);
#   2. it is older than `HUNG_MIN_AGE_S`, which is past every legitimate writer's OWN timeout
#      (the adoption waits 540 s, the shadow sync 600 s), so a slow writer is never a candidate;
#   3. it moved NO CPU and NO I/O across a sampling window -- this is the proof, and it is the
#      one thing an age threshold alone cannot give. A `git gc` on this repository is slow and
#      burns CPU the whole time; it will never be reaped by this;
#   4. it is not this process, and not one of this process's own ancestors.
#
# Everything examined is reported, including what was SPARED and why, because "nothing was hung"
# and "nothing could be measured" must never render identically (L1.28a). Without psutil the
# verdict is UNMEASURED and nothing is killed.

#: Past every legitimate writer's own timeout: Adopt-And-Seal waits 540 s for the mutex, the
#: shadow sync's limit is 600 s. Anything still alive at 30 minutes has already outlived every
#: bound the desk's own writers respect.
HUNG_MIN_AGE_S = 1800.0

#: How long to watch a candidate before calling it stopped. Long enough that a writer between two
#: syscalls still registers, short enough to sit inside the adoption's window.
HUNG_SAMPLE_S = 15.0

#: `sshd` is excluded on purpose -- see note 1 above.
_WRITER_NAMES = frozenset({"git", "git.exe", "ssh", "ssh.exe"})


def _psutil() -> Any:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:
        return None
    return psutil


def _ancestor_pids(psutil_mod: Any) -> set[int]:
    """This process and every parent of it -- never reaped, whatever they look like."""
    pids = {os.getpid()}
    try:
        proc = psutil_mod.Process(os.getpid())
        for parent in proc.parents():
            pids.add(parent.pid)
    except Exception:  # psutil raises a family of its own errors here
        pass
    return pids


def _writer_sample(psutil_mod: Any) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for proc in psutil_mod.process_iter(["pid", "name", "create_time", "cmdline"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name not in _WRITER_NAMES:
                continue
            times = proc.cpu_times()
            try:
                counters = proc.io_counters()
                read_b, write_b = int(counters.read_bytes), int(counters.write_bytes)
            except Exception:  # not every platform exposes per-process I/O
                read_b = write_b = -1
            out[int(proc.info["pid"])] = {
                "pid": int(proc.info["pid"]),
                "name": proc.info["name"],
                "age_s": max(0.0, time.time() - float(proc.info["create_time"] or 0.0)),
                "cpu_s": float(times.user) + float(times.system),
                "read_b": read_b,
                "write_b": write_b,
                "cmd": " ".join(proc.info["cmdline"] or [])[:200],
            }
        except Exception:  # a process that exits mid-iteration is not an error
            continue
    return out


def hung_writers(*, min_age_s: float = HUNG_MIN_AGE_S, sample_s: float = HUNG_SAMPLE_S,
                 sleep: Any = time.sleep) -> dict[str, Any]:
    """Which git/ssh processes are PROVEN stopped, and which were spared and why.

    Returns `{"status": "MEASURED"|"UNMEASURED", "hung": [...], "spared": [...], "why": str}`.
    Measurement only: this function never signals anything.
    """
    rec: dict[str, Any] = {"status": "UNMEASURED", "hung": [], "spared": [],
                           "sample_s": sample_s, "min_age_s": min_age_s, "why": ""}
    psutil_mod = _psutil()
    if psutil_mod is None:
        rec["why"] = ("psutil is not importable here, so no process can be shown to be stopped; "
                      "nothing is reaped on a guess")
        return rec

    protected = _ancestor_pids(psutil_mod)
    first = _writer_sample(psutil_mod)
    old = {pid: row for pid, row in first.items()
           if float(row["age_s"]) >= min_age_s and pid not in protected}
    for pid, row in first.items():
        if pid in protected:
            rec["spared"].append({**row, "why": "this process or one of its own ancestors"})
        elif float(row["age_s"]) < min_age_s:
            rec["spared"].append({
                **row, "why": f"{float(row['age_s']):.0f}s old (< {min_age_s:.0f}s): still "
                              "inside the window a legitimate writer is allowed"})
    if not old:
        rec["status"] = "MEASURED"
        rec["why"] = (f"no git/ssh process is older than {min_age_s:.0f}s, so none can be the "
                      "writer that is holding the lock open")
        return rec

    sleep(sample_s)
    second = _writer_sample(psutil_mod)
    for pid, before in old.items():
        after = second.get(pid)
        if after is None:
            rec["spared"].append({**before, "why": "exited during the sample; it was working"})
            continue
        d_cpu = float(after["cpu_s"]) - float(before["cpu_s"])
        d_io = 0
        if int(before["read_b"]) >= 0 and int(after["read_b"]) >= 0:
            d_io = ((int(after["read_b"]) - int(before["read_b"]))
                    + (int(after["write_b"]) - int(before["write_b"])))
        row = {**after, "d_cpu_s": round(d_cpu, 4), "d_io_b": d_io}
        if d_cpu > 0.0 or d_io > 0:
            rec["spared"].append({
                **row, "why": f"moved {d_cpu:.3f}s of CPU and {d_io}B of I/O in {sample_s:.0f}s: "
                              "slow, not stopped"})
            continue
        rec["hung"].append({
            **row, "why": (f"{float(after['age_s']) / 3600.0:.2f}h old and moved 0.000s of CPU "
                           f"and 0B of I/O across {sample_s:.0f}s: stopped, not slow. It holds "
                           "the index and the writer mutex that every ship step serialises on.")})
    rec["status"] = "MEASURED"
    rec["why"] = (f"{len(rec['hung'])} stopped and {len(rec['spared'])} spared of "
                  f"{len(first)} git/ssh process(es) examined")
    return rec


def reap_hung_writers(*, apply: bool = False, min_age_s: float = HUNG_MIN_AGE_S,
                      sample_s: float = HUNG_SAMPLE_S, sleep: Any = time.sleep,
                      repo: Path | str | None = None) -> dict[str, Any]:
    """Kill the writers `hung_writers` proved stopped, then clear the debris they left.

    `apply=False` (the default) measures and reports and signals nothing, so the decision can
    always be read before it is taken. Returns the measurement plus `killed`, `failed` and the
    `index_lock` record, and it NEVER reports a kill it did not make.
    """
    rec = hung_writers(min_age_s=min_age_s, sample_s=sample_s, sleep=sleep)
    rec["applied"] = apply
    rec["killed"] = []
    rec["failed"] = []
    rec["index_lock"] = {"present": False, "removed": False, "age_s": None,
                         "why": "not attempted"}
    if rec["status"] != "MEASURED" or not rec["hung"] or not apply:
        if rec["status"] == "MEASURED" and rec["hung"] and not apply:
            rec["why"] += "; --apply was not given, so nothing was signalled"
        return rec

    psutil_mod = _psutil()
    if psutil_mod is None:  # pragma: no cover -- hung_writers would already be UNMEASURED
        return rec
    for row in rec["hung"]:
        pid = int(row["pid"])
        try:
            proc = psutil_mod.Process(pid)
            proc.kill()
            proc.wait(timeout=10)
            rec["killed"].append({"pid": pid, "name": row["name"], "cmd": row["cmd"]})
        except Exception as exc:  # the reason matters here, the type does not
            rec["failed"].append({"pid": pid, "name": row["name"],
                                  "why": f"{type(exc).__name__}: {exc}"})
    # Only now is the remaining git population real, so the existing guard means what it says.
    rec["index_lock"] = clear_stale_index_lock(repo if repo is not None else _repo_root())
    return rec
