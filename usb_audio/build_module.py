"""Package the guarded USB audio fix without embedding vendor configuration."""
import argparse
import hashlib
import pathlib
import zipfile

SOURCE = pathlib.Path(__file__).resolve().parent
FILES = ("module.prop", "compat.sh", "customize.sh", "patch.awk", "post-fs-data.sh")


def build_module(output):
    output = pathlib.Path(output)
    payload = {name: (SOURCE / "module" / name).read_bytes() for name in FILES}
    payload["LICENSE"] = (SOURCE.parent / "LICENSE").read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    package = output / "rg556-usb-audio-fix-v1.1.zip"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in payload.items():
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            mode = 0o755 if name == "post-fs-data.sh" else 0o644
            entry.external_attr = (0o100000 | mode) << 16
            archive.writestr(entry, data)
    checksum = hashlib.sha256(package.read_bytes()).hexdigest()
    package.with_suffix(".zip.sha256").write_text(f"{checksum}  {package.name}\n")
    return package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("build/usb-audio"))
    args = parser.parse_args()
    print(build_module(args.output))


if __name__ == "__main__":
    main()
