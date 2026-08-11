import glob
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def find_vcvarsall_by_glob():
    patterns = []
    for envvar in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(envvar)
        if root:
            patterns.append(
                os.path.join(
                    root,
                    "Microsoft Visual Studio",
                    "20[0-9][0-9]",
                    "*",
                    "VC",
                    "Auxiliary",
                    "Build",
                    "vcvarsall.bat",
                )
            )
    paths = sorted(
        (path for pattern in patterns for path in glob.glob(pattern)), reverse=True
    )
    print("glob vcvarsall candidates:")
    for path in paths:
        print(f"  {path}")
    return paths[0] if paths else None


def find_vcvarsall_by_vswhere():
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    if not program_files_x86:
        print("ProgramFiles(x86) is not set")
        return None

    vswhere = os.path.join(
        program_files_x86, "Microsoft Visual Studio", "Installer", "vswhere.exe"
    )
    print(f"vswhere: {vswhere}")
    if not os.path.exists(vswhere):
        print("vswhere.exe does not exist")
        return None

    out = subprocess.check_output(
        [
            vswhere,
            "-latest",
            "-products",
            "*",
            "-find",
            r"VC\Auxiliary\Build\vcvarsall.bat",
            "-utf8",
        ],
        encoding="utf-8",
        errors="replace",
    )
    paths = [line.strip() for line in out.splitlines() if line.strip()]
    print("vswhere vcvarsall candidates:")
    for path in paths:
        print(f"  {path}")
    return paths[0] if paths else None


def capture_vcvars_env(vcvarsall, base_env):
    with tempfile.NamedTemporaryFile(suffix=".cmd", delete=False) as script:
        script_path = Path(script.name)
    try:
        script_path.write_text(
            f'@echo off\r\ncall "{vcvarsall}" amd64 >nul\r\n'
            "if errorlevel 1 exit /b %errorlevel%\r\nset\r\n",
            encoding="mbcs",
        )
        out = subprocess.check_output(
            ["cmd.exe", "/d", "/q", "/c", str(script_path)],
            env=base_env,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        script_path.unlink()

    captured = {}
    for line in out.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            captured[key] = value
    return captured


def first_path(env):
    for key, value in env.items():
        if key.upper() == "PATH":
            return key, value
    return None, None


def main():
    print(f"ImageOS={os.environ.get('ImageOS')}")
    print(f"ImageVersion={os.environ.get('ImageVersion')}")
    print(f"raw shutil.which: {shutil.which('mt.exe')}")

    kits_root = os.environ.get("ProgramFiles(x86)")
    if kits_root:
        mt_glob = os.path.join(kits_root, "Windows Kits", "10", "bin", "*", "x64", "mt.exe")
        print("Windows SDK mt.exe candidates:")
        for path in sorted(glob.glob(mt_glob), reverse=True):
            print(f"  {path}")

    glob_vcvarsall = find_vcvarsall_by_glob()
    vswhere_vcvarsall = find_vcvarsall_by_vswhere()
    vcvarsall = vswhere_vcvarsall or glob_vcvarsall
    if vcvarsall is None:
        raise RuntimeError("vcvarsall.bat not found")
    print(f"selected vcvarsall (vswhere first): {vcvarsall}")

    base_env = dict(os.environ)
    captured = capture_vcvars_env(vcvarsall, base_env)
    merged = dict(base_env)
    merged.update(captured)

    print("PATH-like keys after dict.update:")
    for key, value in merged.items():
        if key.upper() == "PATH":
            print(f"  {key} starts with: {value[:240]}")

    selected_key, selected_path = first_path(merged)
    print(f"build.py env_path selected key: {selected_key}")
    print(f"build.py-style shutil.which: {shutil.which('mt.exe', path=selected_path)}")

    captured_key, captured_path = first_path(captured)
    print(f"vcvars captured PATH key: {captured_key}")
    print(f"vcvars-only shutil.which: {shutil.which('mt.exe', path=captured_path)}")

    canonical = {key: value for key, value in merged.items() if key.upper() != "PATH"}
    canonical["PATH"] = captured_path
    print(f"canonicalized shutil.which: {shutil.which('mt.exe', path=canonical['PATH'])}")


if __name__ == "__main__":
    main()
