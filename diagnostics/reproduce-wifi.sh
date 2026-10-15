#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Run locally on the device, detached from adb. Logs may contain network details.
set -eu
umask 077
HERE=${0%/*}
HELPER=$HERE/standby-cycle
TRACE=/sys/kernel/tracing
GROUP=rg556wifi
INSTANCE=$TRACE/instances/rg556_wifi_repro
OUT=$HERE/results
case "${1:-short}" in
    short) CYCLES='20 30 60'; BATTERY=0 ;;
    --battery) CYCLES='180'; BATTERY=1 ;;
    *) echo 'Usage: reproduce-wifi.sh [--battery]'; exit 1 ;;
esac
[ "$(id -u)" = 0 ] || exit 1
[ "$(getprop ro.product.vendor.model)" = RG556 ] || exit 1
[ "$(getprop ro.lineage.version)" = GammaOS_Next_v1.2 ] || exit 1
[ "$(uname -r)" = 5.4.233 ] || exit 1
[ "$(getprop sys.screen.state)" = on ] || exit 1
[ ! -e "$OUT" ] || { echo 'Use a fresh directory for each run'; exit 1; }
[ ! -e "$INSTANCE" ] || { echo 'Diagnostic trace instance already exists'; exit 1; }
[ ! -e "$TRACE/events/$GROUP" ] || { echo 'Diagnostic probes already exist'; exit 1; }
"$HELPER" --check
mkdir "$OUT"
PROBES=''
CAPTURE=''
RECOVERY=''
CREATED_INSTANCE=0
cleanup() {
    trap - EXIT INT TERM HUP
    [ -z "$CAPTURE" ] || { kill "$CAPTURE" 2>/dev/null || true; wait "$CAPTURE" 2>/dev/null || true; }
    if [ "$CREATED_INSTANCE" = 1 ]; then
        echo 0 > "$INSTANCE/tracing_on" 2>/dev/null || true
        cat "$INSTANCE/trace" > "$OUT/trace-final.txt" 2>/dev/null || true
        echo 0 > "$INSTANCE/events/enable" 2>/dev/null || true
        for event in force_exit legacy_force_exit tx_deinit legacy_deinit card_remove card_remove_request firmware_assert; do
            echo '!stacktrace' > "$INSTANCE/events/$GROUP/$event/trigger" 2>/dev/null || true
        done
        rmdir "$INSTANCE" 2>/dev/null || true
    fi
    for event in $PROBES; do
        printf -- '-:%s/%s\n' "$GROUP" "$event" >> "$TRACE/kprobe_events" 2>/dev/null || true
    done
    /system/bin/input keyevent 224 >/dev/null 2>&1 || true
    [ -z "$RECOVERY" ] || sh "$RECOVERY/service.sh" || true
    echo 'Cleanup completed' >> "$OUT/progress.txt"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

add_probe() {
    name=$1 symbol=$2
    printf 'p:%s/%s %s\n' "$GROUP" "$name" "$symbol" >> "$TRACE/kprobe_events"
    PROBES="$PROBES $name"
}
add_probe force_exit sprd_wlan_combo:sc2355_tx_force_exit
add_probe legacy_force_exit sprd_wlan_combo:sprdwl_force_exit
add_probe tx_deinit sprd_wlan_combo:sc2355_tx_deinit
add_probe legacy_deinit sprd_wlan_combo:sprdwl_tx_deinit
add_probe reset sprd_wlan_combo:sc2355_reset
add_probe card_remove wcn_bsp:sdiohal_remove
add_probe card_remove_request wcn_bsp:sdiohal_remove_card
add_probe bus_suspend wcn_bsp:sdiohal_suspend
add_probe bus_resume wcn_bsp:sdiohal_resume
add_probe firmware_assert wcn_bsp:__wcn_assert_interface
mkdir "$INSTANCE"
CREATED_INSTANCE=1
echo 512 > "$INSTANCE/buffer_size_kb"
echo boot > "$INSTANCE/trace_clock"
for event in force_exit legacy_force_exit tx_deinit legacy_deinit card_remove card_remove_request firmware_assert; do
    echo stacktrace > "$INSTANCE/events/$GROUP/$event/trigger"
done
echo 1 > "$INSTANCE/events/$GROUP/enable"
echo 1 > "$INSTANCE/events/power/suspend_resume/enable"
echo 1 > "$INSTANCE/tracing_on"
"$HELPER" --capture-kernel > "$OUT/kernel.txt" 2>&1 &
CAPTURE=$!

# Pause only the known monitor, and only if it is currently running.
for module in /data/adb/modules/rg556_wifi_recovery /data/adb/modules_update/rg556_wifi_recovery; do
    [ -f "$module/monitor.pid" ] || continue
    pid=$(cat "$module/monitor.pid")
    case "$pid" in ''|*[!0-9]*) continue ;; esac
    if [ "$(readlink "/proc/$pid/exe")" = "$module/bin/rg556-wifi-watch" ]; then
        RECOVERY=$module
        sh "$module/uninstall.sh"
        break
    fi
done

snapshot() {
    label=$1
    /system/bin/timeout 8 /system/bin/cmd wifi status > "$OUT/$label-wifi.txt" 2>&1 || true
    cat /sys/power/suspend_stats/success > "$OUT/$label-suspend-success.txt"
    cat /sys/power/suspend_stats/fail > "$OUT/$label-suspend-fail.txt"
}
snapshot before
grep -q '^Wifi is enabled$' "$OUT/before-wifi.txt" || exit 1
grep -q '^Wifi is connected to ' "$OUT/before-wifi.txt" || exit 1
echo 'Started; recovery monitor paused if present' > "$OUT/progress.txt"
if [ "$BATTERY" = 1 ]; then
    echo 'Waiting for USB disconnect (up to 120 seconds)' >> "$OUT/progress.txt"
    remaining=24
    while :; do
        /system/bin/timeout 5 /system/bin/dumpsys battery > "$OUT/usb-status.txt" 2>&1
        grep -q 'USB powered: false' "$OUT/usb-status.txt" && break
        remaining=$((remaining - 1))
        [ "$remaining" -gt 0 ] || { echo 'USB disconnect timed out' >> "$OUT/progress.txt"; exit 1; }
        sleep 5
    done
    echo 'USB disconnected; settling for five seconds' >> "$OUT/progress.txt"
    sleep 5
    /system/bin/input keyevent 224
fi
cycle=0
for seconds in $CYCLES; do
    cycle=$((cycle + 1))
    echo "Cycle $cycle: requested $seconds seconds" >> "$OUT/progress.txt"
    printf 'cycle_%s_sleep\n' "$cycle" > "$INSTANCE/trace_marker"
    "$HELPER" "$seconds" > "$OUT/cycle-$cycle-timing.txt" 2>&1
    cat "$OUT/cycle-$cycle-timing.txt" >> "$OUT/progress.txt"
    suspended=$(sed -n 's/.*suspended_ms=\([0-9][0-9]*\).*/\1/p' "$OUT/cycle-$cycle-timing.txt")
    if [ -z "$suspended" ] || [ "$suspended" -lt 1000 ]; then
        echo "Cycle $cycle: INVALID as a deep-suspend reproducer (less than one second suspended)" >> "$OUT/progress.txt"
    fi
    sleep 4
    /system/bin/timeout 8 /system/bin/cmd wifi start-scan > "$OUT/cycle-$cycle-scan.txt" 2>&1 || true
    sleep 5
    snapshot "cycle-$cycle"
    cat "$INSTANCE/trace" > "$OUT/cycle-$cycle-trace.txt"
    if grep -q 'hif->exit' "$OUT/kernel.txt" || grep -q 'sc2355_scan failed (-12)' "$OUT/kernel.txt"; then
        echo "Driver failure captured in cycle $cycle; stopping" >> "$OUT/progress.txt"
        break
    fi
    if ! grep -q '^Wifi is connected to ' "$OUT/cycle-$cycle-wifi.txt"; then
        echo "Not connected after cycle $cycle; stopping for inspection" >> "$OUT/progress.txt"
        break
    fi
    echo "Cycle $cycle: connected after wake" >> "$OUT/progress.txt"
done
snapshot after
echo 'Finished' >> "$OUT/progress.txt"
