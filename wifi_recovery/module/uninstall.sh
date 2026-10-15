#!/system/bin/sh
MODDIR=${0%/*}
[ -f "$MODDIR/monitor.pid" ] || exit 0
pid=$(cat "$MODDIR/monitor.pid")
case "$pid" in ''|*[!0-9]*) exit 0 ;; esac
if [ "$(readlink "/proc/$pid/exe")" = "$MODDIR/bin/rg556-wifi-watch" ]; then
    kill "$pid"
fi
