"""Read-only containment for checked upgrade paths, including absent aliases."""
from __future__ import annotations

import os
import sys
import unicodedata
from pathlib import Path

from sbtd_migration_files import _lstat


def _directory_case_sensitive(path: Path) -> bool | None:
    """Read native directory semantics; unknown must not authorize alias writes."""
    try:
        if sys.platform == "darwin":
            # Darwin sys/unistd.h: _PC_CASE_SENSITIVE (not exposed by Python).
            value = os.pathconf(path, 11)
            return bool(value) if value >= 0 else None
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            create = kernel.CreateFileW
            create.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
            ]
            create.restype = wintypes.HANDLE
            query = kernel.GetFileInformationByHandleEx
            query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            query.restype = wintypes.BOOL
            close = kernel.CloseHandle
            close.argtypes = [wintypes.HANDLE]
            close.restype = wintypes.BOOL
            handle = create(str(path), 0x80, 7, None, 3, 0x02200000, None)
            if handle == ctypes.c_void_p(-1).value:
                return None
            try:
                flags = wintypes.ULONG()
                # FileCaseSensitiveInfo, FILE_CS_FLAG_CASE_SENSITIVE_DIR.
                if not query(handle, 23, ctypes.byref(flags), ctypes.sizeof(flags)):
                    return None
                return bool(flags.value & 1)
            finally:
                close(handle)
        if sys.platform.startswith("linux"):
            import array
            import fcntl

            flags = array.array("L", [0])
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                # FS_IOC_GETFLAGS; ext4/f2fs casefold is per-directory.
                request = 0x80000000 | (flags.itemsize << 16) | (ord("f") << 8) | 1
                fcntl.ioctl(fd, request, flags, True)
                return not bool(flags[0] & 0x40000000)
            finally:
                os.close(fd)
    except (OSError, ValueError):
        pass
    return None


def _missing_path_anchor(path: Path) -> tuple[Path, tuple[str, ...]]:
    ancestor = path
    while _lstat(ancestor) is None and str(ancestor.parent) != str(ancestor):
        ancestor = ancestor.parent
    return ancestor, path.parts[len(ancestor.parts):]


def path_contains(path: Path, root: Path) -> bool:
    root_info = _lstat(root)
    for ancestor in (path, *path.parents):
        if str(ancestor) == str(root):
            return True
        info = _lstat(ancestor)
        if (
            root_info is not None and root_info.st_ino
            and info is not None and info.st_ino
            and (info.st_dev, info.st_ino) == (root_info.st_dev, root_info.st_ino)
        ):
            return True
    if root_info is None:
        anchor, tail = _missing_path_anchor(root)
        other_anchor, other_tail = _missing_path_anchor(path)
        anchor_info, other_info = _lstat(anchor), _lstat(other_anchor)
        if (
            anchor_info is not None and anchor_info.st_ino
            and other_info is not None and other_info.st_ino
            and (anchor_info.st_dev, anchor_info.st_ino) == (other_info.st_dev, other_info.st_ino)
            and len(other_tail) >= len(tail)
        ):
            prefix = other_tail[:len(tail)]
            if sys.platform == "darwin":
                # APFS/HFS+ fold canonical Unicode forms even on case-sensitive volumes.
                prefix = tuple(unicodedata.normalize("NFD", part) for part in prefix)
                tail = tuple(unicodedata.normalize("NFD", part) for part in tail)
            if prefix == tail:
                return True
            if tuple(part.casefold() for part in prefix) == tuple(part.casefold() for part in tail):
                return _directory_case_sensitive(anchor) is not True
    return False


def paths_overlap(first: Path, second: Path) -> bool:
    return path_contains(first, second) or path_contains(second, first)
