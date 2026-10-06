"""빌드한 Windows 앱과 설명서·라이선스를 ZIP으로 묶는다. python package_windows.py v0.1.1"""
import hashlib
from importlib.metadata import distribution
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
PACKAGES = ("pymupdf", "olefile", "python-docx", "python-pptx", "openpyxl",
            "beautifulsoup4", "lxml", "pillow", "typing-extensions", "xlsxwriter",
            "et-xmlfile", "soupsieve", "pyinstaller")


def package(version):
    if not re.fullmatch(r"v\d+\.\d+\.\d+", version):
        raise ValueError("버전은 v0.1.1 같은 형식으로 지정합니다.")
    target = ROOT / "dist" / f"PKOS-Windows-{version}.zip"
    entries = {
        "PKOS/PKOS.exe": (ROOT / "dist/PKOS.exe").read_bytes(),
        "PKOS/사용설명서.md": (ROOT / "WINDOWS_사용법.md").read_bytes(),
        "PKOS/LICENSE": (ROOT / "LICENSE").read_bytes(),
    }
    rows = [f"PKOS Windows {version}", f"Python {sys.version.split()[0]}", ""]
    for name in PACKAGES:
        dist = distribution(name)
        licenses = [f for f in dist.files or []
                    if any(part.lower().startswith(("license", "licence", "copying", "notice")) for part in f.parts)
                    and Path(dist.locate_file(f)).is_file()]
        if not licenses:
            raise RuntimeError(f"라이선스 파일을 찾을 수 없습니다: {name}")
        rows.append(f"{name} {dist.version}")
        for i, path in enumerate(licenses):
            entries[f"PKOS/licenses/{name}/{i}-{path.name}"] = Path(dist.locate_file(path)).read_bytes()
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    entries["PKOS/licenses/Python-LICENSE.txt"] = python_license.read_bytes()
    tcl_root = Path(sys.base_prefix) / "tcl"
    tcl_licenses = list(tcl_root.rglob("license.terms"))
    if not tcl_licenses:
        raise RuntimeError("Tcl/Tk 라이선스 파일을 찾을 수 없습니다.")
    for license_path in tcl_licenses:
        entries["PKOS/licenses/tcl/" + license_path.relative_to(tcl_root).as_posix()] = license_path.read_bytes()
    entries["PKOS/licenses/README.txt"] = "\n".join(rows).encode("utf-8")
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    (ROOT / "dist/SHA256SUMS.txt").write_text(f"{checksum}  {target.name}\n", encoding="ascii")
    print(f"{target.name}: {target.stat().st_size:,} bytes, {len(entries)} files")
    print(f"SHA256 {checksum}")


if __name__ == "__main__":
    package(sys.argv[1])
