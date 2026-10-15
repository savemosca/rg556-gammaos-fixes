#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$BOOTMODE" = true ] || abort "Install from the running Magisk app or CLI"
case "$MAGISK_VER_CODE" in
    ''|*[!0-9]*) abort "Cannot determine Magisk version" ;;
esac
[ "$MAGISK_VER_CODE" -ge 30600 ] || abort "Magisk 30.6 or newer required"
. "$MODPATH/compat.sh"
usb_audio_platform_matches || abort "Requires RG556 GammaOS Next 1.2 Full"

usb_audio_mounted=$(usb_audio_hash /vendor/etc/primary_audio_policy_configuration.xml)
case "$usb_audio_mounted" in
    "$USB_AUDIO_ORIGINAL_SHA256"|"$USB_AUDIO_LEGACY_SHA256"|"$USB_AUDIO_PATCHED_SHA256") ;;
    *) abort "Unknown active primary audio policy; resolve other audio overrides first" ;;
esac
[ "$(usb_audio_hash /vendor/etc/usb_audio_policy_configuration.xml)" = "$USB_AUDIO_USB_POLICY_SHA256" ] ||
    abort "Unsupported USB audio policy"

# The running 1.0/1.1 module can mask the original. Read it in a child namespace;
# no denylist settings or mounts of the running audio services are changed.
usb_audio_original="$TMPDIR/usb-system-audio-fix-original.xml"
magisk --denylist exec /system/bin/cat /vendor/etc/primary_audio_policy_configuration.xml > "$usb_audio_original" ||
    abort "Cannot read original policy in an isolated Magisk namespace"
[ "$(usb_audio_hash "$usb_audio_original")" = "$USB_AUDIO_ORIGINAL_SHA256" ] ||
    abort "Unsupported original primary audio policy"

usb_audio_target="$MODPATH/system/vendor/etc/primary_audio_policy_configuration.xml"
mkdir -p "$MODPATH/system/vendor/etc" || abort "Cannot create overlay directory"
awk -f "$MODPATH/patch.awk" "$usb_audio_original" > "$usb_audio_target" || abort "Policy transformation failed"
[ "$(usb_audio_hash "$usb_audio_target")" = "$USB_AUDIO_PATCHED_SHA256" ] ||
    abort "Generated policy differs from the verified result"
rm -f "$usb_audio_original"
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/post-fs-data.sh" 0 0 0755
ui_print "USB routing fix generated and verified; reboot to activate"
