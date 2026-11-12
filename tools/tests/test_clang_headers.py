"""`clang_headers.py`: the committed headers agree with their manifest, and a file that
does not is named. Nothing here reaches the network: the download is monkeypatched."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from sn_tools import clang_headers

pytestmark = pytest.mark.filterwarnings("error")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A checkout-shaped copy of the committed headers, manifest and licence."""
    source = clang_headers.default_root().joinpath(*clang_headers.RESOURCE)
    shutil.copytree(source, tmp_path.joinpath(*clang_headers.RESOURCE))
    return tmp_path


def _directory(root: Path) -> Path:
    return root.joinpath(*clang_headers.RESOURCE)


def test_the_committed_headers_verify() -> None:
    assert clang_headers.main(["--verify"]) == 0


def test_a_changed_missing_or_extra_file_is_named(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    include = _directory(root) / "include"
    (include / "stddef.h").write_bytes(b"/* edited */\n")
    (include / "float.h").unlink()
    (include / "immintrin.h").write_bytes(b"")
    (_directory(root) / "LICENSE.TXT").write_bytes(b"")

    assert clang_headers.main(["--verify", "--root", str(root)]) == 1

    err = capsys.readouterr().err
    assert "include/stddef.h: sha256" in err
    assert "include/float.h is missing" in err
    assert "include/immintrin.h is not in the manifest" in err
    assert "LICENSE.TXT does not match the manifest" in err


CLANG_CMAKE = """\
# Headers shared by Arm and AArch64
set(core_files
  float.h
  stddef.h # trailing comment
  )
set(hlsl_h hlsl.h)
set(cuda_wrapper_files
  cuda_wrappers/new
)
set(files ${core_files})
function(clang_generate_header td_option td_file out_file)
  list(APPEND generated_files "${CMAKE_CURRENT_BINARY_DIR}/${out_file}")
endfunction(clang_generate_header)
set(generated_files)
if(ARM IN_LIST LLVM_TARGETS_TO_BUILD)
  clang_generate_header(-gen-arm-neon arm_neon.td arm_neon.h)
endif()
install(
  FILES ${files} ${generated_files}
  DESTINATION ${header_install_dir}
  COMPONENT clang-resource-headers)
install(
  FILES ${cuda_wrapper_files}
  DESTINATION ${header_install_dir}/cuda_wrappers
  COMPONENT clang-resource-headers)
install(
  FILES ${core_files} unlisted.h
  DESTINATION ${header_install_dir}
  EXCLUDE_FROM_ALL
  COMPONENT core-resource-headers)
if(NOT CLANG_ENABLE_HLSL)
  set(EXCLUDE_HLSL EXCLUDE_FROM_ALL)
endif()
install(
  FILES ${hlsl_h}
  DESTINATION ${header_install_dir}
  ${EXCLUDE_HLSL}
  COMPONENT hlsl-resource-headers)
"""

COMPILER_RT_CMAKE = """\
if (COMPILER_RT_BUILD_XRAY)
  set(XRAY_HEADERS
    xray/xray_interface.h
    )
endif(COMPILER_RT_BUILD_XRAY)
if (COMPILER_RT_BUILD_ORC)
  set(ORC_HEADERS orc_rt/c_api.h)
endif(COMPILER_RT_BUILD_ORC)
install(FILES ${XRAY_HEADERS}
  COMPONENT compiler-rt-headers
  PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ
  DESTINATION ${COMPILER_RT_INSTALL_INCLUDE_DIR}/xray)
install(FILES ${ORC_HEADERS}
  COMPONENT compiler-rt-headers
  DESTINATION ${COMPILER_RT_INSTALL_INCLUDE_DIR}/orc)
"""


def test_the_installed_names_follow_the_default_install_rules() -> None:
    """What a default build installs: the rules' files (variables, generated headers
    and branches taken), at their destination below the include directory, and not
    a rule that is ``EXCLUDE_FROM_ALL``, directly or through a variable; a function's
    body is no rule."""
    assert clang_headers.installed_names(CLANG_CMAKE) == {
        "arm_neon.h",
        "cuda_wrappers/new",
        "float.h",
        "stddef.h",
    }
    assert clang_headers.installed_names(COMPILER_RT_CMAKE) == {
        "orc/c_api.h",
        "xray/xray_interface.h",
    }


def test_a_changed_name_list_or_an_unlisted_header_is_named(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    names = _directory(root) / "names.txt"
    names.write_text(
        "".join(f"{name}\n" for name in names.read_text().split() if name != "stddef.h")
    )

    assert clang_headers.main(["--verify", "--root", str(root)]) == 1

    err = capsys.readouterr().err
    assert "names.txt does not match the manifest" in err
    assert "include/stddef.h is not in names.txt" in err


def test_a_download_rewrites_the_files_and_the_manifest(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bump fetches the manifest's header names, the licence and the CMake lists at
    the new tag, and the result verifies."""
    fetched: list[str] = []
    shipped = " ".join(sorted(clang_headers.read_manifest(_directory(root))[3]))
    clang_cmake = f"install(FILES {shipped} cpuid.h DESTINATION ${{dir}})\n"
    compiler_rt_cmake = "install(FILES xray/x.h DESTINATION ${dir}/xray)\n"

    def fake_fetch(url: str) -> bytes:
        fetched.append(url)
        if url.endswith("clang/lib/Headers/CMakeLists.txt"):
            return clang_cmake.encode()
        if url.endswith("compiler-rt/include/CMakeLists.txt"):
            return compiler_rt_cmake.encode()
        return url.encode()

    monkeypatch.setattr(clang_headers, "fetch", fake_fetch)

    assert clang_headers.main(["--tag", "llvmorg-99.1.0", "--root", str(root)]) == 0

    tag, license_sha, names_sha, headers = clang_headers.read_manifest(_directory(root))
    assert tag == "llvmorg-99.1.0"
    assert len(headers) == 30
    url = clang_headers.SOURCE.format(
        tag="llvmorg-99.1.0", path="clang/lib/Headers/stddef.h"
    )
    assert url in fetched
    assert headers["stddef.h"] == hashlib.sha256(url.encode()).hexdigest()
    assert (
        license_sha
        == hashlib.sha256(
            clang_headers.SOURCE.format(
                tag="llvmorg-99.1.0", path="clang/LICENSE.TXT"
            ).encode()
        ).hexdigest()
    )
    names = (_directory(root) / "names.txt").read_bytes()
    assert names_sha == hashlib.sha256(names).hexdigest()
    assert len(names.split()) == 32
    assert b"xray/x.h\n" in names
