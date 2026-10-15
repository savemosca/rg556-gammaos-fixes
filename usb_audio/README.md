# RG556 USB audio fix 1.1

A guarded update of the existing usb-system-audio-fix Magisk module for the
tested RG556 running GammaOS Next 1.2 Full. It preserves the USB routing of
version 1.0, which the device owner reports worked with their USB accessory.

The original vendor policy declares USB playback and recording devices in both
the primary and USB HALs. This module removes only the primary declarations and
associated routes, so the dedicated USB HAL handles those devices. Speaker,
jack and Bluetooth routing, mix-port profiles and the default output stay the
same. See the [original module review](../docs/usb-audio-module-review.md).

## What changed in 1.1

- Checks RG556 model, GammaOS Next 1.2, Magisk 30.6 or newer, the exact original
  primary policy and the dedicated USB policy before installing.
- Reads the original policy in a separate Magisk namespace, so installation
  over the already active 1.0 or 1.1 overlay works without disabling it first.
- Generates the policy on the device and verifies the result's SHA-256. The ZIP
  contains only the patch and installer sources, not a vendor XML snapshot.
- Refuses an unknown active primary policy, including an unrecognized override
  from another module.
- Checks the device, original policies and generated payload at post-fs-data,
  before Magisk mounts module overlays. An incompatibility creates disable and
  skip_mount markers and records its reason in compatibility-error.txt in the
  module directory. This also protects against a later firmware change.

The boot check is a short one-time script. There is no background service,
timer, audio restart, property override or DSP executable. These checks are
deliberately limited to the verified policies; they do not establish support
for other devices or GammaOS versions. Another audio module installed later
can still conflict with this overlay and needs separate review.

Magisk 30.6's [module boot sequence](https://github.com/topjohnwu/Magisk/blob/v30.6/native/src/core/module.rs)
runs post-fs-data scripts, recollects enabled modules and then applies overlays.
The boot guard uses this ordering. Magisk's
[module documentation](https://topjohnwu.github.io/Magisk/guides.html) describes
the overlay layout and installer hooks used here.

## Download or build

Download the ZIP from the [USB audio v1.1 release](https://github.com/savemosca/rg556-gammaos-fixes/releases/tag/usb-audio-v1.1).
Alternatively, build it with Python 3; no firmware files or Android SDK needed:

    python3 usb_audio/build_module.py

Outputs:

    build/usb-audio/rg556-usb-audio-fix-v1.1.zip
    build/usb-audio/rg556-usb-audio-fix-v1.1.zip.sha256

The builder uses a fixed file list and ZIP metadata. Repeated builds from the
same source produce identical packages. Its checksum file accompanies the ZIP.

## Install, update and remove

Install the ZIP through Magisk's Modules > Install from storage, then reboot.
The ID remains **usb-system-audio-fix**, so this updates version 1.0 in place.
It can also be installed with the running Magisk CLI:

    adb push build/usb-audio/rg556-usb-audio-fix-v1.1.zip /data/local/tmp/
    adb shell su -c 'magisk --install-module /data/local/tmp/rg556-usb-audio-fix-v1.1.zip'
    adb reboot

Disable or remove this module in Magisk and reboot to restore the firmware's
original policy. No audio settings or vendor partition files need restoration.
If the boot guard disabled it after a firmware change, inspect
/data/adb/modules/usb-system-audio-fix/compatibility-error.txt and use a reviewed
compatible version rather than removing the guards.

## Verification

    python3 -m unittest discover -s tests -p test_usb_audio.py -v

Eleven tests cover fresh installation and both overlay updates, rejection of
incompatible devices and policies, failed original-policy access, transformation
failure, output verification, boot-time compatibility, topology preservation
and repeatable source-only packaging. CI uses synthetic policies, not vendor
files or device dumps.

On the RG556, the actual Magisk BusyBox installer logic generated the expected
file in a staging directory while 1.0 remained active. Its SHA-256 was:

    5fab2ab619bbee462e83bd68c3c5ef54d2a3cc86f2dd6b001b52e77cfc8f17a3

The isolated pre-mount boot check passed with the real original vendor policies.
In the staging directory it also disabled an altered payload, then accepted the
verified payload again after a simulated manual re-enable.
The generated XML is semantically identical to the working 1.0 payload; its only
additional changes are indentation and a blank line.

Version 1.1 was subsequently installed through the Magisk CLI and activated by
a real RG556 reboot on 15 October 2026. Boot completed, the compatibility guard
passed, and the mounted policy matched the expected hash above. AudioPolicy
declared all four USB device types only in the dedicated USB module, and the
boot crash log was empty. The original 1.0 module was updated in place.

No USB accessory was attached during this post-reboot verification. The owner's
functional result applies to the 1.0 routing preserved by 1.1; playback and
capture with the accessory have not been independently repeated after this
update.
