"""Compile the optional Android Wi-Fi monitor and package a Magisk module."""
import argparse
import pathlib
import shutil
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", required=True, help="Android NDK aarch64-linux-android29-clang++")
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("build/wifi-recovery"))
    args = parser.parse_args()
    source = pathlib.Path(__file__).resolve().parent
    module = args.output / "module"
    (module / "bin").mkdir(parents=True, exist_ok=True)
    executable = module / "bin/rg556-wifi-watch"
    subprocess.run([
        args.cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O2",
        "-static-libstdc++", str(source / "monitor.cpp"), "-llog", "-o", str(executable)
    ], check=True)
    names = ["module.prop", "customize.sh", "service.sh", "uninstall.sh"]
    for name in names:
        shutil.copyfile(source / "module" / name, module / name)
    package = args.output / "rg556-wifi-recovery-experimental.zip"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as z:
        for name in names + ["bin/rg556-wifi-watch"]:
            z.write(module / name, name)
    print(package)


if __name__ == "__main__":
    main()
