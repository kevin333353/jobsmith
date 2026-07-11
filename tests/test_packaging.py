from pathlib import Path

from packaging_support import conda_runtime_binaries


def test_conda_runtime_binaries_collects_python_dll_dependencies(tmp_path: Path):
    library_bin = tmp_path / "Library" / "bin"
    library_bin.mkdir(parents=True)
    required = {
        "ffi-8.dll",
        "libbz2.dll",
        "libcrypto-3-x64.dll",
        "libexpat.dll",
        "liblzma.dll",
        "libssl-3-x64.dll",
        "sqlite3.dll",
        "zlib.dll",
    }
    for name in required | {"unrelated.dll"}:
        (library_bin / name).touch()

    binaries = conda_runtime_binaries(tmp_path)

    assert {(Path(source).name, destination) for source, destination in binaries} == {
        (name, ".") for name in required
    }
