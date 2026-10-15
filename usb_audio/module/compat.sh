#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
USB_AUDIO_ORIGINAL_SHA256=ba73edff29aad57c56b2848d52df79560a20874553e77b63f7a42b34a35191cc
USB_AUDIO_LEGACY_SHA256=e290d1910ebba0d3e941c93c73753d9af710f58ec1483a45ea77d424fb436634
USB_AUDIO_PATCHED_SHA256=5fab2ab619bbee462e83bd68c3c5ef54d2a3cc86f2dd6b001b52e77cfc8f17a3
USB_AUDIO_USB_POLICY_SHA256=13f6bfaa10b9e77974b0e250fb59e4f583ce0a623766c8cfce1451c96f37afde

usb_audio_hash() {
    sha256sum "$1" 2>/dev/null | cut -d ' ' -f 1
}

usb_audio_platform_matches() {
    [ "$(getprop ro.product.vendor.model)" = RG556 ] &&
    [ "$(getprop ro.lineage.version)" = GammaOS_Next_v1.2 ]
}
