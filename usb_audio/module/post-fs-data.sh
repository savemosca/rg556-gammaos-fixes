#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Magisk 30.6 recollects modules after these scripts, before overlay mounts.
MODDIR=${0%/*}
. "$MODDIR/compat.sh"
usb_audio_reason=''
if ! usb_audio_platform_matches; then
    usb_audio_reason='Device or GammaOS version changed'
elif [ "$(usb_audio_hash /vendor/etc/primary_audio_policy_configuration.xml)" != "$USB_AUDIO_ORIGINAL_SHA256" ]; then
    usb_audio_reason='Original primary audio policy changed'
elif [ "$(usb_audio_hash /vendor/etc/usb_audio_policy_configuration.xml)" != "$USB_AUDIO_USB_POLICY_SHA256" ]; then
    usb_audio_reason='USB audio policy changed'
elif [ "$(usb_audio_hash "$MODDIR/system/vendor/etc/primary_audio_policy_configuration.xml")" != "$USB_AUDIO_PATCHED_SHA256" ]; then
    usb_audio_reason='Module payload differs from the verified result'
fi
if [ -n "$usb_audio_reason" ]; then
    : > "$MODDIR/skip_mount"
    : > "$MODDIR/disable"
    printf '%s\n' "$usb_audio_reason" > "$MODDIR/compatibility-error.txt"
    log -p w -t RG556UsbAudio "$usb_audio_reason; module disabled"
else
    rm -f "$MODDIR/skip_mount" "$MODDIR/compatibility-error.txt"
fi
