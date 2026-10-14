"""Build the experimental rotation module from an exact, locally supplied JAR."""
import argparse
import hashlib
import json
import pathlib
import shutil
import struct
import subprocess
import zipfile
import zlib

EXPECTED_ORIGINAL_SHA256 = "2f4d7f4a228bfa97df109df770ec9cbd1f0a794458ff532f45e8be0fcbfa2474"
PATCH_OFFSET = 0x18A2D4
ORIGINAL_PREFIX = bytes.fromhex(
    "54b00a01 1201 44000001 8700 54a19219 7110283a0100 0a01 b010 "
    "1231 dd050003 3a050400 37150400 2900dd00"
)
PATCHED_PREFIX = bytes.fromhex(
    "54b00a01 1201 44000001 8700 1231 3610ea00 3a00e800 "
    "54a19219 7110283a0100 0a01 b010 dd050003 0000 0000"
)


def patch_dex(original):
    """Preserve method size, registers, branch destinations and exception ranges."""
    if len(ORIGINAL_PREFIX) != len(PATCHED_PREFIX) or len(PATCHED_PREFIX) != 44:
        raise ValueError("Invalid patch size")
    if not original.startswith(b"dex\n"):
        raise ValueError("Not a DEX file")
    if original.count(ORIGINAL_PREFIX) != 1 or original[
        PATCH_OFFSET:PATCH_OFFSET + len(ORIGINAL_PREFIX)
    ] != ORIGINAL_PREFIX:
        raise ValueError("Unexpected framework instructions; refusing to patch")
    dex = bytearray(original)
    dex[PATCH_OFFSET:PATCH_OFFSET + len(ORIGINAL_PREFIX)] = PATCHED_PREFIX
    dex[12:32] = hashlib.sha1(dex[32:]).digest()
    struct.pack_into("<I", dex, 8, zlib.adler32(dex[12:]) & 0xFFFFFFFF)
    return bytes(dex)


def build_module(original, output, zipalign):
    original, output = pathlib.Path(original), pathlib.Path(output)
    # An instruction-pattern match alone cannot establish firmware compatibility.
    if hashlib.sha256(original.read_bytes()).hexdigest() != EXPECTED_ORIGINAL_SHA256:
        raise ValueError("Unsupported services.jar SHA-256; no files were generated")
    with zipfile.ZipFile(original) as zin:
        for name in zin.namelist():
            if name.upper().startswith("META-INF/") and name.upper().endswith(
                (".SF", ".RSA", ".DSA", ".EC")
            ):
                raise ValueError("Signed archive requires separate handling")
        dex = patch_dex(zin.read("classes3.dex"))
        module = output / "rotation-module"
        jar = module / "system/framework/services.jar"
        jar.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(jar, "w") as zout:
            for info in zin.infolist():
                zout.writestr(info, dex if info.filename == "classes3.dex" else zin.read(info.filename))
    aligned = jar.with_suffix(".aligned.jar")
    subprocess.run([str(zipalign), "-f", "4", str(jar), str(aligned)], check=True)
    aligned.replace(jar)
    (module / "module.prop").write_text(
        "id=rg556_rotation_fix\nname=RG556 GammaOS Next 1.2 rotation fix\n"
        "version=0.1-experimental\nversionCode=1\nauthor=savemosca\n"
        "description=Corrects orientation offset and rejects invalid sensor readings. Exact verified Full 1.2 framework only.\n"
    )
    (module / "system.prop").write_text("ro.sensors.sysui_accelerometer_orientation=270\n")
    (module / "customize.sh").write_text(
        '#!/system/bin/sh\n'
        '[ "$(getprop ro.product.vendor.model)" = RG556 ] || abort "RG556 only"\n'
        '[ "$(getprop ro.lineage.version)" = GammaOS_Next_v1.2 ] || abort "GammaOS Next 1.2 only"\n'
        '[ "$(sha256sum /system/framework/services.jar | cut -d\' \' -f1)" = '
        + EXPECTED_ORIGINAL_SHA256
        + ' ] || abort "Framework differs: do not install"\n'
        'set_perm_recursive "$MODPATH" 0 0 0755 0644\n'
    )
    # Exclude any unrelated files left in an existing output directory.
    with zipfile.ZipFile(output / "rg556-rotation-fix-experimental.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for relative in ("module.prop", "system.prop", "customize.sh", "system/framework/services.jar"):
            z.write(module / relative, relative)
    manifest = {
        "device": "RG556", "version": "GammaOS_Next_v1.2 Full",
        "original_services_sha256": EXPECTED_ORIGINAL_SHA256,
        "patched_services_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
        "instruction_offset": hex(PATCH_OFFSET),
        "offset_degrees": 270,
        "status": "Experimental; initial on-device rotation test positive on one RG556",
    }
    (output / "rotation-patch-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=pathlib.Path, default=pathlib.Path("research/services.jar"))
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("build"))
    parser.add_argument("--zipalign", default=shutil.which("zipalign"), help="Android SDK zipalign executable")
    args = parser.parse_args()
    if not args.zipalign:
        parser.error("zipalign not on PATH; supply --zipalign /path/to/Android/sdk/build-tools/VERSION/zipalign")
    try:
        result = build_module(args.input, args.output, args.zipalign)
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Build refused or failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
