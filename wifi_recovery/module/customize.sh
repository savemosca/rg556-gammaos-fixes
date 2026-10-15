#!/system/bin/sh
[ "$(getprop ro.product.vendor.model)" = RG556 ] || abort "RG556 only"
[ "$(getprop ro.lineage.version)" = GammaOS_Next_v1.2 ] || abort "GammaOS Next 1.2 only"
[ -r /dev/kmsg ] || abort "Kernel log access unavailable"
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/bin/rg556-wifi-watch" 0 0 0755
