# Review of the installed USB audio fix

Read-only inspection of one RG556 running GammaOS Next 1.2 Full, 15 October
2026. This reviews the already installed usb-system-audio-fix module, version
1.0, named "USB System Audio Fix (force USB module)". Its metadata lists ChatGPT
as author; it contains only module.prop and one vendor policy XML file.

## Finding

The module makes a narrow, internally consistent routing correction. The
original vendor configuration declares USB devices in both the primary HAL and
the dedicated USB HAL. The module removes the duplicate declarations from
primary, leaving the USB HAL to handle those devices. This is a persistent
configuration change with no background service, periodic restart, DSP library
or executable payload.

[AOSP's HwModuleCollection](https://android.googlesource.com/platform/frameworks/av/+/refs/heads/android14-release/services/audiopolicy/common/managerdefinitions/src/HwModule.cpp)
selects the first module with a profile supporting a device type. The primary
module precedes USB in this device's configuration. Duplicate declarations can
therefore assign USB devices to primary. Removing that ambiguity is consistent
with the stated fix. This source analysis does not prove the original audible
failure without a hardware comparison.

## Exact changes and checks

The original was read in a separate Magisk mount namespace with its overlays
removed for that reader. The active audio services and installed module were
left running. The mounted vendor file is byte-for-byte identical to the module
payload.

| Check | Result |
| --- | --- |
| USB ports removed from primary | USB Device Out, USB Headset Out, USB Device In, USB Headset In |
| Output routes removed from primary | USB Device Out and USB Headset Out |
| Input routes edited | USB sources removed from primary input and recognition input |
| Other XML content | Semantically identical after ignoring formatting and comments |
| Mix-port profiles, attached devices and default speaker | Unchanged |
| Primary and USB route endpoints | All resolve to ports with the expected source/sink roles |
| Dedicated USB configuration | Retains all four removed device types and their routes |
| Effective Android configuration | audio_policy_configuration_a2dp_offload_disabled.xml; includes the patched primary file and USB policy |
| Runtime AudioPolicy state | Primary has no USB device declarations; USB module loaded with handle 26 |

SHA-256 fingerprints of primary_audio_policy_configuration.xml:

    original: ba73edff29aad57c56b2848d52df79560a20874553e77b63f7a42b34a35191cc
    patched:  e290d1910ebba0d3e941c93c73753d9af710f58ec1483a45ea77d424fb436634

The USB HAL exposes dynamic device profiles. USB microphones are affected by
the change as well as USB playback. The policy supplies ordinary USB mix ports;
it does not establish lower latency, hardware offload or improved sound quality.

The speaker, 3.5 mm jack and Bluetooth declarations are preserved. DisplayPort /
HDMI has a separate dp module and is not changed by this fix. GammaEQ was
enabled at inspection; the separate JamesDSP and Audio Modification Library
modules were disabled.

## Limits and integration

The device owner reports that version 1.0 worked when they tested it. No USB
audio endpoint was available in the review's runtime snapshot, and the USB HAL
reported no input or output streams. The independent checks establish that
Android loaded the intended topology; they do not repeat the owner's accessory
test. Recording, output switching and reconnect/resume remain useful extended
checks where those have not already been tested.

The inspected 1.0 module carries a complete static copy of the vendor XML and has
no custom installer compatibility guard. It could replace a newer firmware's
policy with an older snapshot. A reusable installer should verify the device
and original policy fingerprint, or transform and validate the device's current
policy with explicit compatibility checks. [Version 1.1](../usb_audio/README.md)
now implements the guarded transformation and an additional boot-time check.

A native RG556 image can apply these same semantic edits to its **vendor audio
policy**, preserving unrelated device-specific configuration. Merely rebuilding
a system-only GSI does not modify the existing vendor file. No replacement
audio driver or framework JAR is required for this policy correction. Native
integration and accessory validation have not been performed by this project.

Vendor XML and raw audio-service dumps remain in ignored local research/
storage. The vendor XML retains its own Unisoc license notice and is not
redistributed here.
