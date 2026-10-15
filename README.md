# RG556 GammaOS fixes

Experimental, unofficial rotation repair for **Anbernic RG556 running GammaOS Next 1.2 Full**.

This repository contains source, a guarded module builder, verification and rollback tools. Firmware images, original framework files, device identifiers and diagnostic dumps are kept local.

## Status

| Area | Result |
| --- | --- |
| Screen rotation | Initial on-device test positive after installing the module and rebooting one RG556. Extended testing remains open. |
| Joystick noise | A separate built-in 5% deadzone setting eliminated 1,478 ABS events in a four-second resting sample. This setting is not part of the rotation module. |
| Automatic scrolling after wake | Still under investigation; a short wake test is not proof of a fix. |
| Standby battery consumption | Still under investigation. No battery fix is claimed. |
| Wi-Fi unavailable after standby | SC2355 driver failure captured; Android subsystem recovery restored connectivity. Separate experimental automatic recovery available; next-failure validation pending. |
| USB audio | Owner reports the existing 1.0 routing works. [Version 1.1](usb_audio/README.md) preserves it and adds installer and boot-time compatibility checks. Generation verified on the RG556 in staging; real reboot with 1.1 not yet tested. |
| GammaOS 1.4.4 | No RG556 image has been built or released by this project. |

See [Wi-Fi failure analysis and optional automatic recovery](docs/wifi-recovery.md)
for the separate module, its narrow error matching, rate limits and removal.

## What the rotation repair changes

1. Sets the RG556-specific window-orientation offset to 270 degrees.
2. Rejects invalid TYPE_DEVICE_ORIENTATION readings before adding the offset and wrapping into the 0–3 rotation range.

The original framework validates the result after masking it with 3. That check cannot reject an unknown reading such as -1, because the mask has already turned it into a valid rotation.

The source-level correction is in [reject-invalid-orientation.patch](reject-invalid-orientation.patch). It fixes validation; the device-specific offset is a separate configuration change.

## Exact compatibility

The module builder and installer support only the original services.jar with this SHA-256:

    2f4d7f4a228bfa97df109df770ec9cbd1f0a794458ff532f45e8be0fcbfa2474

This was extracted from the December 2025 GammaOS Next 1.2 Full build tested on RG556. Other builds, Lite, other devices and modified frameworks are rejected.

The binary patch is not portable to a newer Android framework. **Disable this module and reboot before upgrading to a different firmware or extracting an unpatched original.** Do not remove the compatibility checks to force installation.

## Build locally

Requirements: Python 3, Android SDK Build Tools with zipalign, and your own matching original services.jar. ADB is needed only to obtain the framework and install or remove the module.

Select your device explicitly:

    adb devices -l
    export ANDROID_SERIAL=YOUR_RG556_SERIAL

If the rotation module is already active, disable it and reboot before extracting the original. A pull while it is active retrieves the patched overlay and will fail the builder's hash check.

    mkdir -p research
    adb pull /system/framework/services.jar research/services.jar

Build and verify:

    python3 build_rotation_fix.py --input research/services.jar --zipalign /path/to/Android/sdk/build-tools/VERSION/zipalign
    python3 verify_rotation_patch.py

If zipalign is already on PATH, its argument can be omitted. Generated files are under build/, including:

- rg556-rotation-fix-experimental.zip
- rotation-module/
- rotation-patch-manifest.json

Neither the original nor the generated module is committed to this repository.

## Install

This replaces a core framework file through a Magisk overlay. Keep a working backup and a recovery method before testing. The original file on the system partition is not overwritten.

On the matching rooted device:

    adb push build/rg556-rotation-fix-experimental.zip /data/local/tmp/rg556-rotation-fix-experimental.zip
    adb shell su -c 'magisk --install-module /data/local/tmp/rg556-rotation-fix-experimental.zip'
    adb reboot

The installer checks the device model, GammaOS version and original framework hash. Check rotation in all four directions in an app that supports auto-rotation.

## Roll back

Disable "RG556 GammaOS Next 1.2 rotation fix" in Magisk and reboot, or use:

    sh restore.sh
    adb reboot

The restore script accepts --serial DEVICE or the ANDROID_SERIAL environment variable. ADB itself refuses an ambiguous connection when multiple devices are attached.

The optional --reset-deadzone flag also sets the old GammaPad deadzone to zero. Use it only if you intend to revert that separate setting; by default rollback leaves your controller settings alone.

## Verification

Without any firmware files:

    python3 -m unittest discover -s tests -v
    python3 verify_rotation_patch.py --self-test

With a locally built module:

    python3 verify_rotation_patch.py

Verification covers 36 control-flow cases using the actual patched DEX instruction bytes: all four offsets, valid rotations, unknown readings and out-of-range values. Full module verification additionally checks the precise DEX changes, SHA-1/Adler-32 checksums and unchanged JAR entries. The build preserves method size, register usage and existing branch destinations.

During the initial device test, the patched framework also passed Android dex2oat verification, ZIP alignment checks, reboot and an initial physical rotation check. CI does not contain firmware binaries and cannot replace on-device testing.

## Upstream contribution

The source patch targets:

    frameworks/base/services/core/java/com/android/server/wm/WindowOrientationListener.java

From a compatible GammaOS source checkout:

    git apply --check /path/to/rg556-gammaos-fixes/reject-invalid-orientation.patch
    git apply /path/to/rg556-gammaos-fixes/reject-invalid-orientation.patch

A contribution to the framework belongs in a fork of [GammaOSNextDistribution-14](https://github.com/TheGammaSqueeze/GammaOSNextDistribution-14), which contains the Android sources. The separate [GammaOSNext](https://github.com/TheGammaSqueeze/GammaOSNext) repository hosts distribution information and issue tracking.

Related reports: [rotation #168](https://github.com/TheGammaSqueeze/GammaOSNext/issues/168), [wake scrolling #249](https://github.com/TheGammaSqueeze/GammaOSNext/issues/249), [standby drain #277](https://github.com/TheGammaSqueeze/GammaOSNext/issues/277).

## License

Repository code is provided under Apache-2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE). Upstream authors retain their copyrights. Locally supplied firmware components remain subject to their own applicable licenses.
