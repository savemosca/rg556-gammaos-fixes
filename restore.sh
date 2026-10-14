#!/bin/sh
# Disable this module. Reboot is deliberately left to the user.
set -eu
device_serial=$(printenv ANDROID_SERIAL || true)
reset_deadzone=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --serial)
            [ "$#" -ge 2 ] || { printf '%s\n' 'Missing serial' >&2; exit 2; }
            device_serial=$2
            shift 2
            ;;
        --reset-deadzone) reset_deadzone=1; shift ;;
        *) printf '%s\n' 'Usage: sh restore.sh [--serial DEVICE] [--reset-deadzone]' >&2; exit 2 ;;
    esac
done
device_adb() {
    if [ -n "$device_serial" ]; then
        adb -s "$device_serial" "$@"
    else
        adb "$@"
    fi
}
model=$(device_adb shell getprop ro.product.vendor.model | tr -d '\r')
[ "$model" = RG556 ] || { printf '%s\n' 'Refusing: target is not an RG556' >&2; exit 1; }
device_adb shell 'su -c "if [ -d /data/adb/modules/rg556_rotation_fix ]; then touch /data/adb/modules/rg556_rotation_fix/disable; fi; if [ -d /data/adb/modules_update/rg556_rotation_fix ]; then touch /data/adb/modules_update/rg556_rotation_fix/disable; fi"'
if [ "$reset_deadzone" -eq 1 ]; then
    device_adb shell 'su -c "setprop persist.gammaos.analogdeadzone 0; echo 0 > /data/GammaPad/DEADZONE"'
fi
printf '%s\n' 'Module disabled. Reboot the RG556 to restore its original framework.'
