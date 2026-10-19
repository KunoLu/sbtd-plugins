"""Safe filesystem primitives for the SBTD batch-migration runtime.

The migration planner/phase orchestrator owns manifest authorization and
operation attribution. This module owns the physical side: canonical absolute
paths, nofollow regular-file reads, real type detection, complete directory
state (every entry and empty directory included, no cache exclusions),
verified private storage, and compare-before-write commits.

Directory state follows the PRD wire format: the complete entry array
(every entry and empty directory, no cache exclusions), globally sorted by
relative POSIX path, with streamed file checksums and null directory
checksums; the directory digest is the SHA-256 of that array's canonical
JSON. Hashing and copying stream in chunks, so large binary attachments
are never read whole; only ``read_file`` materializes bytes for callers
that must parse content.

Honest limits, by design:

- Directory copies are entry-by-entry. A failed directory install or backup
  is reported as partial; multi-file atomicity is never claimed.
- Directory replacement happens only behind a caller-supplied backup that
  is complete, current and inside a verified private directory; a differing
  existing directory without such a backup is a conflict, never a silent
  delete of unrelated paths.
- Privacy uses real platform semantics: POSIX ownership plus mode bits, or
  an in-process Win32 owner and DACL proof on Windows. Any
  platform or state that cannot be proven fails closed; a chmod is never
  treated as ACL evidence.
- Directory creation followed by ACL installation assumes a trusted,
  single-controller parent namespace. Handle identity proof binds the
  path at open time; it does not make mkdir plus ACL installation atomic.
- Callers take the original target backup (``backup_reference``) before
  ``install_reference`` changes anything, and keep manifest authorization.

Errors are sanitized ``ContractError`` failures: fixed rule text, never
rejected values or private path content.
"""

from __future__ import annotations

import contextlib
import ctypes
import functools
import hashlib
import os
import stat
import tempfile
import types
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, NoReturn

from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_project import TaskDataError, open_regular_file

__all__ = [
    "RetainedObjectError",
    "backup_reference",
    "directory_snapshot",
    "install_reference",
    "read_file",
    "remove_reference",
    "require_private_directory",
    "save_document",
    "snapshot",
    "write_file",
]

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CHUNK = 1024 * 1024
_STATE_KEYS = {"type", "checksum"}
_REFERENCE_KEYS = {"path", "state"}
_HEX_DIGITS = frozenset("0123456789abcdef")
_ABSENT = {"type": "absent", "checksum": None}
CreatedEntry = tuple[Path, str, str | None]


class RetainedObjectError(ContractError):
    """A failed cutover retained an unexpected object, not a trusted backup."""

    def __init__(self, path: Path, *other_paths: Path) -> None:
        super().__init__(
            "foreign-content-conflict",
            "a cutover needs explicit reconciliation of its recorded retained paths",
            exit_code=5,
        )
        self.retained_refs: list[dict[str, Any]] = []
        for retained in (path, *other_paths):
            try:
                state = snapshot(retained)
            except (ContractError, OSError, RuntimeError):
                state = None
            self.retained_refs.append({"path": str(retained), "state": state})


def _fail(code: str, message: str, *, exit_code: int = 2) -> NoReturn:
    raise ContractError(code, message, exit_code=exit_code)


# ---------------------------------------------------------------------------
# Canonical paths, type detection and safe reads
# ---------------------------------------------------------------------------


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _canonical(path: Path) -> Path:
    """Require a physical absolute path without resolving untrusted links."""
    candidate = Path(path)
    if not candidate.is_absolute() or ".." in candidate.parts:
        _fail("unsafe-path", "migration paths must be canonical and absolute")
    current = Path(candidate.anchor)
    for index, part in enumerate(candidate.parts[1:]):
        current = current / part
        info = _lstat(current)
        if info is None:
            continue
        if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
            _fail(
                "unsafe-path", "migration paths do not follow symbolic or reparse links"
            )
        if index < len(candidate.parts) - 2 and not stat.S_ISDIR(info.st_mode):
            _fail("unsafe-path", "a migration parent is not a directory")
    return candidate


def _lstat(path: Path) -> os.stat_result | None:
    """lstat where genuine absence is distinct from every real error."""
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        _fail("read-failed", "path cannot be inspected")


def _read_regular(path: Path) -> bytes:
    """Nofollow regular-file read; only for callers that need the bytes."""
    try:
        with open_regular_file(path, "migration file") as handle:
            return handle.read()
    except TaskDataError:
        _fail("read-failed", "file cannot be read safely")


def _hash_file(path: Path) -> str:
    """Streaming SHA-256 of one nofollow regular file."""
    digest = hashlib.sha256()
    try:
        with open_regular_file(path, "migration file") as handle:
            while chunk := handle.read(_CHUNK):
                digest.update(chunk)
    except TaskDataError:
        _fail("read-failed", "file cannot be read safely")
    return digest.hexdigest()


def _contained(path: Path, root: Path) -> bool:
    return path.is_relative_to(root)


def _bytes_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------------------
# Complete directory state (one walk shared by both snapshot interfaces)
# ---------------------------------------------------------------------------


def _list_children(directory: Path) -> list[os.DirEntry]:
    try:
        with os.scandir(directory) as listing:
            children = list(listing)
    except OSError:
        _fail("read-failed", "directory entries cannot be listed")
    children.sort(key=lambda entry: os.fsencode(entry.name))
    return children


def _scan_into(directory: Path, prefix: str, entries: list[dict[str, Any]]) -> None:
    for child in _list_children(directory):
        name = child.name
        relative = name if not prefix else f"{prefix}/{name}"
        try:
            info = child.stat(follow_symlinks=False)
        except OSError:
            _fail("read-failed", "directory entry cannot be inspected")
        child_path = Path(child.path)
        if _is_reparse(info):
            _fail("unsafe-path", "directory contains a link or special entry")
        if stat.S_ISDIR(info.st_mode):
            entries.append({"path": relative, "type": "directory", "checksum": None})
            _scan_into(child_path, relative, entries)
        elif stat.S_ISREG(info.st_mode):
            entries.append(
                {
                    "path": relative,
                    "type": "file",
                    "checksum": _hash_file(child_path),
                }
            )
        else:
            _fail("unsafe-path", "directory contains a link or special entry")


def _scan_directory(root: Path) -> tuple[str, list[dict[str, Any]]]:
    """One walk producing the PRD flat wire digest and every canonical entry.

    The directory checksum is the SHA-256 of the canonical JSON of the
    complete entry array, globally sorted by relative POSIX path. Directory
    entries carry a null checksum; file entries carry the streamed content
    digest. Every entry and empty directory is included, nothing is
    excluded and there is no cross-call cache.
    """
    entries: list[dict[str, Any]] = []
    try:
        _scan_into(root, "", entries)
    except RecursionError:
        _fail("unsafe-path", "directory tree is deeper than the traversal limit")
    entries.sort(key=lambda entry: entry["path"])
    checksum = hashlib.sha256(canonical_json_bytes(entries)).hexdigest()
    return checksum, entries


# ---------------------------------------------------------------------------
# Contract state validation
# ---------------------------------------------------------------------------


def _expect_state(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("invalid-argument", "state must be a mapping with type and checksum")
    if set(value) - _STATE_KEYS or not _STATE_KEYS.issubset(value):
        _fail("invalid-argument", "state must carry exactly type and checksum")
    kind = value["type"]
    checksum = value["checksum"]
    if kind not in ("absent", "file", "directory"):
        _fail("invalid-argument", "state type is not absent, file or directory")
    if kind == "absent":
        if checksum is not None:
            _fail("invalid-argument", "absent state cannot carry a checksum")
    elif not (
        isinstance(checksum, str)
        and len(checksum) == 64
        and _HEX_DIGITS.issuperset(checksum)
    ):
        _fail("invalid-argument", "state checksum is not a lowercase SHA-256 digest")
    return {"type": kind, "checksum": checksum}


def _reference(source_ref: object) -> tuple[Path, dict[str, Any]]:
    if not isinstance(source_ref, Mapping):
        _fail("invalid-argument", "reference must be a mapping with path and state")
    if set(source_ref) - _REFERENCE_KEYS or not _REFERENCE_KEYS.issubset(source_ref):
        _fail("invalid-argument", "reference must carry exactly path and state")
    path = source_ref["path"]
    if not isinstance(path, str) or not path:
        _fail("invalid-argument", "reference path must be a non-empty string")
    state = _expect_state(source_ref["state"])
    if state["type"] == "absent":
        _fail("invalid-argument", "reference state must describe a present object")
    return Path(path), state


# ---------------------------------------------------------------------------
# Public read interfaces
# ---------------------------------------------------------------------------


def snapshot(path: Path) -> dict[str, Any]:
    """Contract state for one path: absent, file or directory.

    Genuine absence returns the absent state; inspection errors raise. Links
    and special files are never reported as absent. The directory branch
    reuses the same complete walk as ``directory_snapshot``; file hashing
    streams, so large binaries are never read whole.
    """
    target = _canonical(path)
    info = _lstat(target)
    if info is None:
        return dict(_ABSENT)
    if stat.S_ISREG(info.st_mode):
        return {"type": "file", "checksum": _hash_file(target)}
    if stat.S_ISDIR(info.st_mode):
        checksum, _ = _scan_directory(target)
        return {"type": "directory", "checksum": checksum}
    _fail("unsafe-path", "path is a link or special file, not absent")


def directory_snapshot(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Directory state plus the exact canonical entries behind its digest.

    Each entry is ``{"path", "type", "checksum"}`` where ``path`` is a POSIX
    path relative to the directory root (join it with the root for safe
    reads), ``type`` is file or directory, and ``checksum`` is the streamed
    file content digest or null for directories. Entries are globally
    sorted by path, include empty directories and exclude nothing; the root
    checksum is the SHA-256 of their canonical JSON. Genuine absence
    returns the absent state and no entries; links, special entries and
    file targets raise.
    """
    target = _canonical(path)
    info = _lstat(target)
    if info is None:
        return dict(_ABSENT), []
    if stat.S_ISREG(info.st_mode):
        _fail("invalid-argument", "directory_snapshot target is a file")
    if not stat.S_ISDIR(info.st_mode):
        _fail("unsafe-path", "directory_snapshot target is a link or special file")
    checksum, entries = _scan_directory(target)
    return {"type": "directory", "checksum": checksum}, entries


def read_file(path: Path, expected: Mapping[str, Any] | None = None) -> bytes:
    """Bytes from one safe nofollow read, optionally bound to a file state."""
    content = _read_regular(_canonical(path))
    if expected is not None:
        reference = _expect_state(expected)
        if reference["type"] != "file":
            _fail("invalid-argument", "expected state must describe a file")
        if reference["checksum"] != _bytes_checksum(content):
            _fail("state-conflict", "file content differs from its expected state")
    return content


# ---------------------------------------------------------------------------
# Private storage and scopes
# ---------------------------------------------------------------------------


# Windows privacy proof, in process through the Win32 security API. The
# directory is opened without following reparse points, bound to the
# object the path names at check time, and its security descriptor read
# from that handle. Nothing is cached between calls.
_TRUSTED_SID_STRINGS = ("S-1-5-18", "S-1-5-32-544")  # SYSTEM, Administrators
_READ_CONTROL = 0x00020000
_WRITE_DAC = 0x00040000
_WRITE_OWNER = 0x00080000
_FILE_SHARE_ALL = 0x00000007
_OPEN_EXISTING = 3
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_TOKEN_QUERY = 0x0008
_TOKEN_USER_CLASS = 1
_SE_FILE_OBJECT = 1
_OWNER_SECURITY_INFORMATION = 0x00000001
_DACL_SECURITY_INFORMATION = 0x00000004
_PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
_ACL_REVISION = 2
_ACL_SIZE_INFORMATION_CLASS = 2
_ACCESS_ALLOWED_ACE_TYPE = 0
_OBJECT_AND_CONTAINER_INHERIT = 0x01 | 0x02
_FILE_ALL_ACCESS = 0x001F01FF


@functools.cache
def _win32() -> Any:
    """Typed Win32 bindings; only built on Windows, never on other hosts."""
    import msvcrt
    from ctypes import wintypes as w

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    void = ctypes.c_void_p
    out = ctypes.POINTER(ctypes.c_void_p)

    def bind(library: Any, name: str, restype: Any, *argtypes: Any) -> Any:
        function = getattr(library, name)
        function.restype = restype
        function.argtypes = argtypes
        return function

    class AceHeader(ctypes.Structure):
        _fields_ = [
            ("AceType", ctypes.c_ubyte),
            ("AceFlags", ctypes.c_ubyte),
            ("AceSize", w.WORD),
        ]

    class AclSizeInformation(ctypes.Structure):
        _fields_ = [
            ("AceCount", w.DWORD),
            ("AclBytesInUse", w.DWORD),
            ("AclBytesFree", w.DWORD),
        ]

    return types.SimpleNamespace(
        msvcrt=msvcrt,
        wintypes=w,
        AceHeader=AceHeader,
        AclSizeInformation=AclSizeInformation,
        CreateFileW=bind(
            kernel32,
            "CreateFileW",
            w.HANDLE,
            w.LPCWSTR,
            w.DWORD,
            w.DWORD,
            void,
            w.DWORD,
            w.DWORD,
            w.HANDLE,
        ),
        CloseHandle=bind(kernel32, "CloseHandle", w.BOOL, w.HANDLE),
        LocalFree=bind(kernel32, "LocalFree", void, void),
        GetCurrentProcess=bind(kernel32, "GetCurrentProcess", w.HANDLE),
        OpenProcessToken=bind(
            advapi32,
            "OpenProcessToken",
            w.BOOL,
            w.HANDLE,
            w.DWORD,
            ctypes.POINTER(w.HANDLE),
        ),
        GetTokenInformation=bind(
            advapi32,
            "GetTokenInformation",
            w.BOOL,
            w.HANDLE,
            ctypes.c_int,
            void,
            w.DWORD,
            ctypes.POINTER(w.DWORD),
        ),
        GetSecurityInfo=bind(
            advapi32,
            "GetSecurityInfo",
            w.DWORD,
            w.HANDLE,
            ctypes.c_int,
            w.DWORD,
            out,
            out,
            out,
            out,
            out,
        ),
        SetSecurityInfo=bind(
            advapi32,
            "SetSecurityInfo",
            w.DWORD,
            w.HANDLE,
            ctypes.c_int,
            w.DWORD,
            void,
            void,
            void,
            void,
        ),
        ConvertStringSidToSidW=bind(
            advapi32, "ConvertStringSidToSidW", w.BOOL, w.LPCWSTR, out
        ),
        IsValidSid=bind(advapi32, "IsValidSid", w.BOOL, void),
        EqualSid=bind(advapi32, "EqualSid", w.BOOL, void, void),
        GetLengthSid=bind(advapi32, "GetLengthSid", w.DWORD, void),
        IsValidAcl=bind(advapi32, "IsValidAcl", w.BOOL, void),
        GetAclInformation=bind(
            advapi32, "GetAclInformation", w.BOOL, void, void, w.DWORD, ctypes.c_int
        ),
        GetAce=bind(advapi32, "GetAce", w.BOOL, void, w.DWORD, out),
        InitializeAcl=bind(advapi32, "InitializeAcl", w.BOOL, void, w.DWORD, w.DWORD),
        AddAccessAllowedAceEx=bind(
            advapi32,
            "AddAccessAllowedAceEx",
            w.BOOL,
            void,
            w.DWORD,
            w.DWORD,
            w.DWORD,
            void,
        ),
    )


_WIN32_FAILURES = (OSError, ValueError, TypeError, ctypes.ArgumentError)


def _win32_check(succeeded: Any) -> None:
    if not succeeded:
        raise OSError("windows security call failed")


@contextlib.contextmanager
def _win32_directory(path: Path, access: int) -> Iterator[int]:
    """Handle to exactly the real directory ``path`` names right now."""
    api = _win32()
    expected = os.lstat(path)
    handle = api.CreateFileW(
        str(path),
        access,
        _FILE_SHARE_ALL,
        None,
        _OPEN_EXISTING,
        _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise OSError("directory cannot be opened")
    try:
        descriptor = api.msvcrt.open_osfhandle(handle, os.O_RDONLY)
    except OSError:
        api.CloseHandle(handle)
        raise
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or getattr(opened, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
            or not os.path.samestat(opened, expected)
        ):
            raise OSError("opened object is not the named real directory")
        yield handle
    finally:
        os.close(descriptor)


@contextlib.contextmanager
def _win32_current_user_sid() -> Iterator[Any]:
    api = _win32()
    w = api.wintypes
    token = w.HANDLE()
    _win32_check(
        api.OpenProcessToken(api.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token))
    )
    try:
        needed = w.DWORD()
        api.GetTokenInformation(token, _TOKEN_USER_CLASS, None, 0, ctypes.byref(needed))
        buffer = ctypes.create_string_buffer(needed.value)
        _win32_check(
            api.GetTokenInformation(
                token, _TOKEN_USER_CLASS, buffer, needed, ctypes.byref(needed)
            )
        )
    finally:
        api.CloseHandle(token)
    sid = ctypes.c_void_p.from_buffer(buffer)
    _win32_check(sid.value and api.IsValidSid(sid))
    yield sid


@contextlib.contextmanager
def _win32_well_known_sids() -> Iterator[list[Any]]:
    api = _win32()
    sids: list[Any] = []
    try:
        for text in _TRUSTED_SID_STRINGS:
            sid = ctypes.c_void_p()
            _win32_check(api.ConvertStringSidToSidW(text, ctypes.byref(sid)))
            sids.append(sid)
        yield sids
    finally:
        for sid in sids:
            api.LocalFree(sid)


def _win32_acl_private(handle: int, me: Any, trusted: list[Any]) -> bool:
    api = _win32()
    owner, dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    status = api.GetSecurityInfo(
        handle,
        _SE_FILE_OBJECT,
        _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
        ctypes.byref(owner),
        None,
        ctypes.byref(dacl),
        None,
        ctypes.byref(descriptor),
    )
    try:
        if status != 0:
            return False
        if not owner.value or not api.IsValidSid(owner) or not api.EqualSid(owner, me):
            return False
        # A NULL DACL grants everyone everything.
        if not dacl.value or not api.IsValidAcl(dacl):
            return False
        size = api.AclSizeInformation()
        _win32_check(
            api.GetAclInformation(
                dacl,
                ctypes.byref(size),
                ctypes.sizeof(size),
                _ACL_SIZE_INFORMATION_CLASS,
            )
        )
        for index in range(size.AceCount):
            ace = ctypes.c_void_p()
            _win32_check(api.GetAce(dacl, index, ctypes.byref(ace)))
            header = api.AceHeader.from_address(ace.value)
            if header.AceType != _ACCESS_ALLOWED_ACE_TYPE:
                return False
            # ACCESS_ALLOWED_ACE: header, access mask, then the SID.
            sid = ctypes.c_void_p(ace.value + ctypes.sizeof(header) + 4)
            if not api.IsValidSid(sid):
                return False
            if not any(api.EqualSid(sid, candidate) for candidate in (me, *trusted)):
                return False
        return True
    finally:
        if descriptor.value:
            api.LocalFree(descriptor)


def _windows_acl_proven(path: Path) -> bool:
    """True only when the directory's own ACL proves a trusted private scope.

    The owner must be the current user and every ACE an allow for the
    current user, SYSTEM or Administrators. Any other ACE type, a NULL
    DACL, or anything unreadable fails closed.
    """
    try:
        with (
            _win32_directory(path, _READ_CONTROL) as handle,
            _win32_current_user_sid() as me,
            _win32_well_known_sids() as trusted,
        ):
            return _win32_acl_private(handle, me, trusted)
    except _WIN32_FAILURES:
        return False


def _windows_make_private(path: Path) -> bool:
    """Own a directory this run just created and give it a protected DACL.

    The DACL holds a single inheritable FullControl allow for the current
    user and inherits nothing from the parent.
    """
    try:
        with (
            _win32_directory(path, _READ_CONTROL | _WRITE_DAC | _WRITE_OWNER) as handle,
            _win32_current_user_sid() as me,
        ):
            api = _win32()
            # ACL header + ACCESS_ALLOWED_ACE (its SidStart overlaps the SID).
            size = (8 + 8 + api.GetLengthSid(me) + 3) & ~3
            acl = ctypes.create_string_buffer(size)
            _win32_check(api.InitializeAcl(acl, size, _ACL_REVISION))
            _win32_check(
                api.AddAccessAllowedAceEx(
                    acl,
                    _ACL_REVISION,
                    _OBJECT_AND_CONTAINER_INHERIT,
                    _FILE_ALL_ACCESS,
                    me,
                )
            )
            status = api.SetSecurityInfo(
                handle,
                _SE_FILE_OBJECT,
                _OWNER_SECURITY_INFORMATION
                | _DACL_SECURITY_INFORMATION
                | _PROTECTED_DACL_SECURITY_INFORMATION,
                me,
                None,
                acl,
                None,
            )
            return status == 0
    except _WIN32_FAILURES:
        return False


def require_private_directory(path: Path, *, create: bool = False) -> Path:
    """Verified private directory, or explicit creation and privatization of one.

    The path itself must always be a real directory, never a link. POSIX
    proof uses current-user ownership plus mode bits with no group/other
    access. Windows proof reads the directory's own security descriptor
    through a handle bound to that directory (``_windows_acl_proven``): the owner must
    be the current user and every ACE an allow for the current user,
    SYSTEM or Administrators; anything unreadable or unknown fails closed.
    ACLs are only ever set on a directory this call created itself, never
    on pre-existing paths. Other platforms fail closed; a chmod is never
    treated as ACL evidence.
    """
    target = _canonical(path)
    info = _lstat(target)
    created = False
    if info is None:
        if not create:
            _fail("privacy-unproven", "private directory does not exist")
        try:
            os.mkdir(target, 0o700)
        except FileExistsError:
            pass
        except OSError:
            _fail("write-failed", "private directory cannot be created")
        else:
            created = True
        info = _lstat(target)
        if info is None:
            _fail("write-failed", "private directory cannot be created")
    if not stat.S_ISDIR(info.st_mode):
        _fail("privacy-unproven", "private path is not a real directory")
    if os.name == "posix":
        if stat.S_IMODE(info.st_mode) & 0o077:
            _fail("privacy-unproven", "private directory grants group or other access")
        if info.st_uid != os.geteuid():
            _fail(
                "privacy-unproven", "private directory is not owned by the current user"
            )
    elif os.name == "nt":
        if created and not _windows_make_private(target):
            _fail("write-failed", "new private directory could not be privatized")
        if not _windows_acl_proven(target):
            _fail(
                "privacy-unproven",
                "private directory access control cannot be proven private",
            )
    else:
        _fail(
            "privacy-unproven",
            "private directory privacy cannot be proven on this platform",
        )
    return target


def _scope_root(scope: Path) -> Path:
    resolved = _canonical(scope)
    info = _lstat(resolved)
    if info is None or not stat.S_ISDIR(info.st_mode):
        _fail("scope-violation", "scope is not an existing directory")
    return resolved


def _target_in_scope(path: Path, scope: Path) -> Path:
    root = _scope_root(scope)
    target = _canonical(path)
    if target == root:
        _fail("invalid-argument", "operation target is the scope root")
    if not _contained(target, root):
        _fail("scope-violation", "target resolves outside the authorized scope")
    return target


# ---------------------------------------------------------------------------
# Streaming copies with metadata preservation
# ---------------------------------------------------------------------------


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _apply_metadata(source: Path, target: Path) -> None:
    info = source.lstat()
    try:
        os.chmod(target, stat.S_IMODE(info.st_mode))
        os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns))
    except OSError:
        _fail("write-failed", "original file metadata cannot be preserved")


def _copy_file_fresh(source: Path, target: Path) -> str:
    """Create a streamed copy and return the checksum of bytes we wrote."""
    created = False
    digest = hashlib.sha256()
    try:
        with open_regular_file(source, "migration file") as source_handle:
            descriptor = os.open(
                target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600
            )
            created = True
            with os.fdopen(descriptor, "wb") as target_handle:
                while chunk := source_handle.read(_CHUNK):
                    written = target_handle.write(chunk)
                    if written != len(chunk):
                        _fail("write-failed", "copy did not accept the complete chunk")
                    digest.update(chunk)
                target_handle.flush()
                os.fsync(target_handle.fileno())
            _apply_metadata(source, target)
        return digest.hexdigest()
    except (TaskDataError, ContractError, OSError) as error:
        if created:
            try:
                remove_reference(
                    target,
                    {"type": "file", "checksum": digest.hexdigest()},
                    scope=target.parent,
                )
            except (ContractError, OSError):
                raise RetainedObjectError(target) from None
        if isinstance(error, ContractError):
            raise
        if isinstance(error, TaskDataError):
            _fail("read-failed", "file cannot be read safely")
        _fail(
            "write-failed",
            "copy could not be completed without overwriting unknown content",
        )


def _tree_entries(root: Path) -> list[tuple[str, str, Path]]:
    entries: list[tuple[str, str, Path]] = []
    stack = [root]
    while stack:
        current = stack.pop()
        for child in _list_children(current):
            try:
                info = child.stat(follow_symlinks=False)
            except OSError:
                _fail("read-failed", "directory entry cannot be inspected")
            child_path = Path(child.path)
            relative = child_path.relative_to(root).as_posix()
            if _is_reparse(info):
                _fail("unsafe-path", "directory contains a link or special entry")
            if stat.S_ISDIR(info.st_mode):
                entries.append((relative, "directory", child_path))
                stack.append(child_path)
            elif stat.S_ISREG(info.st_mode):
                entries.append((relative, "file", child_path))
            else:
                _fail("unsafe-path", "directory contains a link or special entry")
    entries.sort(key=lambda item: item[0])
    return entries


def _copy_tree_fresh(source: Path, target: Path, created: list[CreatedEntry]) -> None:
    """Entry-by-entry tree copy into a fresh target; not atomic and never so claimed."""
    try:
        os.mkdir(target, 0o700)
    except OSError:
        _fail("write-failed", "directory copy target cannot be created")
    created.append((target, "directory", None))
    _populate_tree(source, target, created)


def _populate_tree(
    source: Path,
    target: Path,
    created: list[CreatedEntry],
    *,
    preserve_root_metadata: bool = True,
) -> None:
    """Populate an existing empty target with the complete source tree."""
    entries = _tree_entries(source)
    directories = [(source, target)]
    for relative, kind, entry in entries:
        destination = target / relative
        if kind == "directory":
            try:
                os.mkdir(destination, 0o700)
            except OSError:
                _fail("write-failed", "directory copy target cannot be created")
            created.append((destination, "directory", None))
            directories.append((entry, destination))
        else:
            checksum = _copy_file_fresh(entry, destination)
            created.append((destination, "file", checksum))
    # Directory metadata last, children before parents, so populating the
    # tree cannot disturb preserved timestamps.
    for source_dir, target_dir in reversed(directories):
        if target_dir == target and not preserve_root_metadata:
            continue
        _apply_metadata(source_dir, target_dir)


def _remove_created(created: list[CreatedEntry]) -> bool:
    """Rollback only unchanged written bytes; retain changed or unknown entries."""
    complete = True
    for path, kind, checksum in reversed(created):
        try:
            if kind == "file":
                remove_reference(
                    path, {"type": "file", "checksum": checksum}, scope=path.parent
                )
            else:
                os.rmdir(path)
        except FileNotFoundError:
            continue
        except RetainedObjectError:
            raise
        except (ContractError, OSError):
            complete = False
    return complete


def _fresh_sibling(parent: Path, prefix: str) -> Path:
    """A unique currently-absent sibling name for a controlled rename."""
    holder = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    os.rmdir(holder)
    return holder


def _remove_staging(staging: Path, created: list[CreatedEntry]) -> None:
    try:
        complete = _remove_created(created)
        if complete:
            staging.rmdir()
            return
    except (ContractError, OSError):
        pass
    raise RetainedObjectError(staging)


def _verified_replacement_backup(
    backup_ref: Mapping[str, Any] | None,
    before: dict[str, Any],
    destination: Path,
) -> Path:
    """Proven complete private backup of exactly the expected before-state."""
    if backup_ref is None:
        _fail(
            "state-conflict",
            "existing directory differs from the source and no backup was supplied",
        )
    backup_path, backup_state = _reference(backup_ref)
    if backup_state != before:
        _fail(
            "state-conflict",
            "replacement backup does not match the expected before-state",
        )
    backup = _canonical(backup_path)
    if snapshot(backup) != backup_state:
        _fail("state-conflict", "replacement backup changed since its recorded state")
    require_private_directory(backup.parent)
    if backup.is_relative_to(destination) or destination.is_relative_to(backup):
        _fail("invalid-argument", "replacement backup overlaps its target")
    return backup


def _private_sibling(parent: Path, prefix: str) -> Path:
    holder = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    try:
        if os.name == "nt" and not _windows_make_private(holder):
            _fail("privacy-unproven", "a staging directory could not be made private")
        require_private_directory(holder)
    except ContractError:
        try:
            holder.rmdir()
        except OSError:
            raise RetainedObjectError(holder) from None
        raise
    return holder


def _stage_tree(
    source: Path, expected: dict[str, Any], parent: Path
) -> tuple[Path, list[CreatedEntry]]:
    staging = _private_sibling(parent, ".sbtd-migration-stage-")
    created: list[CreatedEntry] = []
    try:
        _populate_tree(source, staging, created, preserve_root_metadata=False)
        if snapshot(staging) != expected:
            _fail(
                "preservation-failed",
                "complete staged directory differs from its approved image",
                exit_code=3,
            )
    except ContractError:
        _remove_staging(staging, created)
        raise
    return staging, created


def _capture_and_remove_file(
    target: Path, before: Mapping[str, Any], *, holder: Path | None = None
) -> None:
    """Capture the name before verification so a public-name swap is retained."""
    own_holder = holder is None
    if holder is None:
        holder = _private_sibling(target.parent, ".sbtd-migration-held-")
    held = holder / "original"
    if _lstat(held) is not None:
        raise RetainedObjectError(holder)
    try:
        os.rename(target, held)
    except OSError:
        if own_holder:
            holder.rmdir()
        _fail("write-failed", "the owned file could not be captured for removal")
    try:
        unchanged = snapshot(held) == before
    except ContractError:
        unchanged = False
    if not unchanged or _lstat(target) is not None:
        # A hard link restores the captured object without overwriting a new
        # public name. Once restored, discard only our extra link.
        try:
            os.link(held, target, follow_symlinks=False)
        except (OSError, NotImplementedError):
            raise RetainedObjectError(held) from None
        try:
            held.unlink()
            if own_holder:
                holder.rmdir()
        except OSError:
            raise RetainedObjectError(holder) from None
        _fail(
            "foreign-content-conflict",
            "a replacement was restored without deleting its content",
        )
    held.unlink()
    if own_holder:
        holder.rmdir()


def _add_note(error: BaseException, note: str) -> None:
    if hasattr(error, "add_note"):
        error.add_note(note)
    else:  # Python 3.10: same attribute 3.11+ tracebacks render.
        error.__notes__ = [*getattr(error, "__notes__", []), note]


def _release_removal_holder(holder: Path, identity: os.stat_result) -> None:
    """Remove only the same empty directory we created, never unknown entries."""
    observed = _lstat(_canonical(holder))
    if observed is None or not os.path.samestat(identity, observed):
        raise RetainedObjectError(holder)
    try:
        holder.rmdir()
    except OSError:
        raise RetainedObjectError(holder) from None


def _remove_directory_files(target: Path, entries: list[dict[str, Any]]) -> None:
    # Reuse only a same-parent, same-operation holder. ACLs are checked afresh
    # before every capture; no privacy result survives across files or calls.
    holder: Path | None = None
    identity: os.stat_result | None = None
    files = sorted(
        (entry for entry in entries if entry["type"] == "file"),
        key=lambda entry: (str(Path(entry["path"]).parent), entry["path"]),
    )
    try:
        for entry in files:
            member = _target_in_scope(target / entry["path"], target)
            if holder is None or holder.parent != member.parent:
                if holder is not None:
                    previous, holder = holder, None
                    assert identity is not None
                    _release_removal_holder(previous, identity)
                candidate = _private_sibling(member.parent, ".sbtd-migration-held-")
                try:
                    identity = candidate.lstat()
                except OSError:
                    raise RetainedObjectError(candidate) from None
                holder = candidate
            observed = _lstat(_canonical(holder))
            if observed is None or not os.path.samestat(identity, observed):
                raise RetainedObjectError(holder)
            require_private_directory(holder)
            if next(holder.iterdir(), None) is not None:
                raise RetainedObjectError(holder)
            state = {"type": "file", "checksum": entry["checksum"]}
            if snapshot(member) != state:
                _fail(
                    "foreign-content-conflict",
                    "a captured entry changed during owned removal",
                )
            _capture_and_remove_file(member, state, holder=holder)
    except RetainedObjectError:
        # Preserve the primary retained path (possibly holder/original) and
        # its evidence instead of replacing it with a failed rmdir diagnostic.
        holder = None
        raise
    except BaseException as primary:
        # Keep the in-flight error primary; a failed release is only a note.
        if holder is not None:
            assert identity is not None
            pending, holder = holder, None
            try:
                _release_removal_holder(pending, identity)
            except RetainedObjectError as retained:
                # Callers and receipts record retained_refs; surface the
                # retained holder and chain the original error as the cause.
                _add_note(
                    retained,
                    f"raised while handling original error: {primary!r}",
                )
                raise retained from primary
            except Exception as release_error:
                _add_note(
                    primary,
                    f"removal holder release also failed: {release_error!r}",
                )
        raise
    finally:
        if holder is not None:
            assert identity is not None
            _release_removal_holder(holder, identity)


def remove_reference(path: Path, expected: Mapping[str, Any], *, scope: Path) -> None:
    """Remove only the captured entries; concurrent additions are retained.

    Callers preserve the original first. This is a single-controller operation,
    not a cross-process transaction: partial removal is reported, never hidden.
    """
    target = _target_in_scope(path, scope)
    before = _expect_state(expected)
    if before["type"] == "directory":
        current, entries = directory_snapshot(target)
    else:
        current, entries = snapshot(target), []
    if current != before:
        _fail("state-conflict", "owned removal target changed before execution")
    if before["type"] == "absent":
        return
    try:
        if before["type"] == "file":
            _capture_and_remove_file(target, before)
            return
        _remove_directory_files(target, entries)
        directories = sorted(
            (entry for entry in entries if entry["type"] == "directory"),
            key=lambda entry: len(Path(entry["path"]).parts),
            reverse=True,
        )
        for entry in directories:
            member = _target_in_scope(target / entry["path"], target)
            info = _lstat(member)
            if info is None or not stat.S_ISDIR(info.st_mode):
                _fail(
                    "foreign-content-conflict",
                    "a captured directory changed during owned removal",
                )
            member.rmdir()
        target.rmdir()
    except OSError:
        _fail(
            "foreign-content-conflict",
            "owned removal stopped; unapproved or unavailable entries were retained",
        )


def _replace_directory(
    source: Path,
    source_state: dict[str, Any],
    destination: Path,
    before: dict[str, Any],
) -> None:
    """Controlled directory replacement behind an already verified backup.

    The complete candidate is staged in the target's parent and read back
    first, the before-state is re-verified, and only then is the original
    set aside and the candidate moved in. Failure before the swap keeps the
    original; failure during the swap restores it; anything unrecoverable
    is reported as partial with the original surviving in the verified
    backup. No cross-process compare-and-swap is claimed.
    """
    parent = destination.parent
    staging, created = _stage_tree(source, source_state, parent)
    try:
        if snapshot(destination) != before:
            _fail(
                "state-conflict",
                "install target changed while the replacement was staged",
            )
    except ContractError:
        _remove_staging(staging, created)
        raise
    retired = _fresh_sibling(parent, ".sbtd-migration-retired-")
    try:
        os.rename(destination, retired)
    except OSError:
        _remove_staging(staging, created)
        _fail(
            "write-failed",
            "directory replacement could not set the original aside; the original was preserved",
        )
    try:
        if snapshot(retired) != before:
            _fail(
                "foreign-content-conflict",
                "the set-aside original changed during replacement",
            )
    except ContractError:
        if _lstat(destination) is None:
            try:
                os.rename(retired, destination)
            except OSError:
                raise RetainedObjectError(retired) from None
        _remove_staging(staging, created)
        if _lstat(retired) is not None:
            raise RetainedObjectError(retired) from None
        raise
    try:
        os.rename(staging, destination)
    except OSError:
        try:
            os.rename(retired, destination)
        except OSError:
            raise RetainedObjectError(retired) from None
        _fail(
            "write-failed",
            "directory replacement failed before commit; the original was restored",
        )
    if snapshot(destination) != source_state:
        damaged: Path | None = None
        try:
            damaged = _fresh_sibling(parent, ".sbtd-migration-damaged-")
            os.rename(destination, damaged)
            os.rename(retired, destination)
        except OSError:
            retained = [retired, destination]
            if damaged is not None:
                retained.append(damaged)
            raise RetainedObjectError(*retained) from None
        raise RetainedObjectError(damaged)
    # Recheck and remove only the captured old entries. A changed set-aside
    # tree is retained and reported; recursive deletion would erase new work.
    try:
        remove_reference(retired, before, scope=parent)
    except ContractError as error:
        if isinstance(error, RetainedObjectError):
            raise
        raise RetainedObjectError(retired) from None


# ---------------------------------------------------------------------------
# Staged atomic file commits
# ---------------------------------------------------------------------------


def _stage(parent: Path, content: bytes) -> str:
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".sbtd-migration-", dir=parent)
    except OSError:
        _fail("write-failed", "staged write cannot be prepared")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        _unlink_quiet(Path(temporary))
        _fail("write-failed", "staged write cannot be prepared")
    return temporary


def _stage_copy(source: Path, parent: Path) -> str:
    """Stream one verified source file into a same-directory staging file."""
    temporary: str | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".sbtd-migration-", dir=parent)
        with (
            open_regular_file(source, "migration file") as source_handle,
            os.fdopen(descriptor, "wb") as target_handle,
        ):
            while chunk := source_handle.read(_CHUNK):
                target_handle.write(chunk)
            target_handle.flush()
            os.fsync(target_handle.fileno())
    except TaskDataError:
        if temporary is not None:
            _unlink_quiet(Path(temporary))
        _fail("read-failed", "file cannot be read safely")
    except OSError:
        if temporary is not None:
            _unlink_quiet(Path(temporary))
        _fail("write-failed", "staged write cannot be prepared")
    return temporary  # type: ignore[return-value]


def _commit_staged(
    target: Path,
    temporary: str,
    before: dict[str, Any],
    mode_source: Path | None,
    expected_checksum: str,
) -> None:
    """Atomic commit of a staged file against an expected before-state.

    Absent targets use a no-overwrite create; existing targets are replaced
    only while their state still matches ``before``. Any failure before the
    commit point leaves the known original untouched; the commit is proven
    by a streamed readback against ``expected_checksum``.
    """
    pending: str | None = temporary
    try:
        if _hash_file(Path(pending)) != expected_checksum:
            _fail(
                "preservation-failed",
                "staged candidate differs from its approved bytes; no publication occurred",
                exit_code=3,
            )
        if snapshot(target) != before:
            _fail("state-conflict", "target changed while the write was staged")
        mode_info = None
        if mode_source is not None:
            mode_info = _lstat(mode_source)
        elif before["type"] == "file":
            mode_info = _lstat(target)
        if mode_info is not None:
            try:
                os.chmod(pending, stat.S_IMODE(mode_info.st_mode))
            except OSError:
                _fail(
                    "write-failed",
                    "file mode cannot be carried onto the staged write",
                )
        try:
            if before["type"] == "absent":
                os.link(pending, target)
            else:
                os.replace(pending, target)
                pending = None
        except FileExistsError:
            _fail("state-conflict", "target appeared during a no-overwrite create")
        except OSError:
            _fail(
                "write-failed",
                "write commit failed; the original content was preserved",
            )
    finally:
        if pending is not None:
            _unlink_quiet(Path(pending))
    if _hash_file(target) != expected_checksum:
        _fail(
            "preservation-failed",
            "committed content failed readback verification",
            exit_code=3,
        )


# ---------------------------------------------------------------------------
# Public mutation interfaces
# ---------------------------------------------------------------------------


def backup_reference(
    source_ref: Mapping[str, Any], destination: Path, *, private_root: Path
) -> dict[str, Any]:
    """Preserve one complete original inside a verified private root.

    The source must still match its recorded state. A present destination is
    reused only when it is already the same complete original (state and
    private containment proven); any other existing content is a conflict
    and is preserved, never overwritten. Fresh copies stream, preserve
    metadata inside the private ancestor and read back against the source
    state; originals and empty directories survive intact.
    """
    source_path, source_state = _reference(source_ref)
    private = require_private_directory(private_root)
    source = _canonical(source_path)
    if snapshot(source) != source_state:
        _fail("state-conflict", "backup source changed since its recorded state")
    target = _canonical(destination)
    if not _contained(target, private):
        _fail("scope-violation", "backup destination resolves outside the private root")
    if target.is_relative_to(source):
        _fail("invalid-argument", "backup destination overlaps its source")
    parent_info = _lstat(target.parent)
    if parent_info is None or not stat.S_ISDIR(parent_info.st_mode):
        _fail("write-failed", "backup destination parent is not an existing directory")
    existing = snapshot(target)
    if existing["type"] != "absent":
        if existing == source_state:
            return {"path": str(target), "state": existing}
        _fail(
            "state-conflict",
            "backup destination already holds different content and was preserved",
        )
    created: list[CreatedEntry] = []
    try:
        if source_state["type"] == "file":
            checksum = _copy_file_fresh(source, target)
            created.append((target, "file", checksum))
        else:
            _copy_tree_fresh(source, target, created)
    except ContractError:
        if _remove_created(created):
            _fail(
                "write-failed",
                "backup copy failed before completion; the incomplete copy was removed",
            )
        _fail(
            "write-failed",
            "backup copy failed before completion; an incomplete copy may remain",
        )
    readback = snapshot(target)
    if readback != source_state:
        removed = _remove_created(created)
        _fail(
            "preservation-failed",
            "backup readback does not match the source state"
            + (
                "; the incomplete copy was removed"
                if removed
                else "; an incomplete copy may remain"
            ),
            exit_code=3,
        )
    return {"path": str(target), "state": readback}


def write_file(
    path: Path, content: bytes, expected: Mapping[str, Any], *, scope: Path
) -> None:
    """Write one file inside ``scope`` against its expected before-state.

    An originally absent target is created without overwrite; an existing
    file is replaced atomically only while it still matches ``expected``.
    Unknown target or user changes are rejected and the known original is
    kept on every failure.
    """
    if not isinstance(content, (bytes, bytearray)):
        _fail("invalid-argument", "write content must be bytes")
    payload = bytes(content)
    before = _expect_state(expected)
    if before["type"] == "directory":
        _fail("invalid-argument", "write_file cannot replace a directory")
    target = _target_in_scope(path, scope)
    if snapshot(target) != before:
        _fail("state-conflict", "write target changed before the authorized write")
    temporary = _stage(target.parent, payload)
    _commit_staged(target, temporary, before, None, _bytes_checksum(payload))


def install_reference(
    source_ref: Mapping[str, Any],
    target: Path,
    expected: Mapping[str, Any],
    *,
    scope: Path,
    backup_ref: Mapping[str, Any] | None = None,
) -> None:
    """Install one verified source file or directory at ``target``.

    The complete source is re-verified against its reference first. File
    targets stage a streamed copy and commit atomically against
    ``expected``. Directory targets are created entry-by-entry (partial
    failure is reported honestly, never as atomic). An existing directory
    identical to the source is already installed; a differing one is
    replaced only behind ``backup_ref`` — a caller-taken complete backup
    whose state matches ``expected`` exactly and which lives inside a
    verified private directory — and otherwise refused, never silently
    deleting unrelated paths. Multi-resource transactions are not claimed.
    """
    source_path, source_state = _reference(source_ref)
    source = _canonical(source_path)
    if snapshot(source) != source_state:
        _fail("state-conflict", "install source changed since its recorded state")
    before = _expect_state(expected)
    destination = _target_in_scope(target, scope)
    if snapshot(destination) != before:
        _fail("state-conflict", "install target changed before the authorized install")
    if source_state["type"] == "file":
        if before["type"] == "directory":
            _fail("state-conflict", "a file cannot replace an existing directory")
        temporary = _stage_copy(source, destination.parent)
        _commit_staged(destination, temporary, before, source, source_state["checksum"])
        return
    if before["type"] == "file":
        _fail("state-conflict", "a directory cannot replace an existing file")
    if before["type"] == "directory":
        if before["checksum"] == source_state["checksum"]:
            return
        if destination.is_relative_to(source):
            _fail("invalid-argument", "install destination lies inside its source")
        _verified_replacement_backup(backup_ref, before, destination)
        _replace_directory(source, source_state, destination, before)
        return
    if destination.is_relative_to(source):
        _fail("invalid-argument", "install destination lies inside its source")
    staging, staged_entries = _stage_tree(source, source_state, destination.parent)
    created: list[CreatedEntry] = []
    failure: ContractError | None = None
    try:
        if snapshot(destination) != before:
            _fail("state-conflict", "directory target changed before publication")
        # Reserve an absent name, then copy only from our complete verified
        # private stage. Rename could overwrite a competing empty directory.
        _copy_tree_fresh(staging, destination, created)
        _apply_metadata(source, destination)
        if snapshot(destination) != source_state:
            _fail(
                "preservation-failed",
                "installed directory changed during readback",
                exit_code=3,
            )
    except ContractError as error:
        failure = error
    retained: list[Path] = []
    if failure is not None:
        try:
            if not _remove_created(created):
                retained.append(destination)
        except ContractError:
            retained.append(destination)
    try:
        _remove_staging(staging, staged_entries)
    except ContractError:
        retained.append(staging)
    if retained:
        raise RetainedObjectError(retained[0], *retained[1:])
    if failure is not None:
        raise failure


def save_document(
    path: Path, document: Mapping[str, Any], *, private_root: Path
) -> dict[str, Any]:
    """Canonical-JSON atomic save of a new document inside a private root.

    Existing content is never overwritten: receipts stay immutable. The file
    is staged with fsync, committed without overwrite and read back; the
    returned object reference describes what is actually on disk.
    """
    if not isinstance(document, Mapping):
        _fail("invalid-argument", "document must be a mapping")
    payload = canonical_json_bytes(document)
    private = require_private_directory(private_root)
    target = _canonical(path)
    if target == private or not _contained(target, private):
        _fail("scope-violation", "document path resolves outside the private root")
    parent_info = _lstat(target.parent)
    if parent_info is None or not stat.S_ISDIR(parent_info.st_mode):
        _fail("write-failed", "document parent is not an existing directory")
    if _lstat(target) is not None:
        _fail("state-conflict", "document already exists and was preserved")
    temporary = _stage(target.parent, payload)
    _commit_staged(target, temporary, dict(_ABSENT), None, _bytes_checksum(payload))
    return {
        "path": str(target),
        "state": {"type": "file", "checksum": _bytes_checksum(payload)},
    }
