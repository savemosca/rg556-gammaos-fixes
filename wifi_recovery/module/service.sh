#!/system/bin/sh
MODDIR=${0%/*}
[ -f "$MODDIR/disable" ] && exit 0
[ -f "$MODDIR/remove" ] && exit 0
[ "$(getprop ro.product.vendor.model)" = RG556 ] || exit 1
[ "$(getprop ro.lineage.version)" = GammaOS_Next_v1.2 ] || exit 1
count=0
while [ "$(getprop sys.boot_completed)" != 1 ]; do
    count=$((count + 1))
    [ "$count" -lt 120 ] || exit 1
    sleep 1
done
/system/bin/cmd wifi help 2>&1 | grep -q 'trigger-recovery' || exit 1
if [ -f "$MODDIR/monitor.pid" ]; then
    previous=$(cat "$MODDIR/monitor.pid")
    case "$previous" in
        ''|*[!0-9]*) ;;
        *) [ "$(readlink "/proc/$previous/exe")" = "$MODDIR/bin/rg556-wifi-watch" ] && exit 0 ;;
    esac
fi
"$MODDIR/bin/rg556-wifi-watch" </dev/null >/dev/null 2>&1 &
printf '%s\n' "$!" > "$MODDIR/monitor.pid"
