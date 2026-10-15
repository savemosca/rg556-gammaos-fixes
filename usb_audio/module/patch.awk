# SPDX-License-Identifier: Apache-2.0
# Only run on the exact original policy accepted by compat.sh.
/^[[:space:]]*<devicePort tagName="USB (Device|Headset) (Out|In)" / {
    ports++
    next
}
/^[[:space:]]*<route type="mix" sink="USB (Device|Headset) Out"$/ {
    if (skip) exit 1
    skip = 1
    routes++
    next
}
skip {
    if ($0 !~ /^[[:space:]]*sources="primary output,compressed_offload,fast,voip_rx"\/>$/) exit 1
    skip = 0
    next
}
{
    if ($0 ~ /,USB (Device|Headset) In/) {
        inputs++
        gsub(/,USB Device In/, "")
        gsub(/,USB Headset In/, "")
    }
    print
}
END {
    if (skip || ports != 4 || routes != 2 || inputs != 2) exit 1
}
