"""Helpers used by PyInstaller release specifications."""
from pathlib import Path

_CONDA_RUNTIME_DLLS = (
    "ffi-8.dll",
    "libbz2.dll",
    "libcrypto-3-x64.dll",
    "libexpat.dll",
    "liblzma.dll",
    "libssl-3-x64.dll",
    "sqlite3.dll",
    "zlib.dll",
)


def conda_runtime_binaries(base_prefix: str | Path) -> list[tuple[str, str]]:
    """Return conda's Python runtime DLLs for inclusion beside a frozen executable."""
    library_bin = Path(base_prefix) / "Library" / "bin"
    if not library_bin.is_dir():
        return []
    available = {path.name.lower(): path for path in library_bin.glob("*.dll")}
    return [
        (str(available[name]), ".")
        for name in _CONDA_RUNTIME_DLLS
        if name in available
    ]
