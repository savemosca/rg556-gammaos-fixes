# Wi-Fi unavailable after standby

Observed on an RG556 with GammaOS Next 1.2 Full, 15 October 2026.

## Captured failure

The Wi-Fi toggle remained enabled, the supplicant was disconnected, wlan0 had no
IP address, and every scan failed. The kernel reported:

    sprd-wlan: sc2355_tx_get_msg can not get msg: hif->exit
    sprd-wlan: sc2355_get_cmdbuf, 736, fail to get msg, mode=1
    wlan0: sc2355_scan failed (-12)

CMD52/CMD5 errors on the SDIO host appeared immediately after a suspend exit,
before the first captured driver-exit failure. Android exposed the scan error as
"Out of memory", but several GiB of system memory were available. The message
alone is not evidence of exhausted Android RAM. The driver/SDIO resume cause
still needs investigation.

Root recovery was tested directly:

    adb shell su -c 'cmd wifi trigger-recovery'

It restarted the Wi-Fi subsystem, preserved the enabled setting and saved
networks, and restored both association and an Android-validated Internet
connection. A short disabled/transitional state during restart is expected.

Related upstream report:
[GammaOSNextDistribution-14 #6](https://github.com/TheGammaSqueeze/GammaOSNextDistribution-14/issues/6).
The Wi-Fi sleep fix for RG DS Plus is for different hardware and is not proof of
an RG556 driver fix.

## Optional automatic recovery

The separate experimental module rg556_wifi_recovery follows **new** /dev/kmsg
records. It requests the tested Android recovery command only when:

- both the SC2355 hif->exit and scan -12 signatures occur within five seconds;
- the screen is on;
- Android still reports Wi-Fi enabled;
- at least three minutes have passed since its previous request, with at most
  two requests in a one-hour window.

It skips historical kernel records on startup, discards a pending fault when the
driver is reinitialized, and does not treat ordinary disconnections or a missing
access point as a fault. Screen changes use a blocking property notification;
the monitor holds no wakelock and has no periodic polling timer. It does not
record SSIDs, addresses, credentials or raw kernel records. Only static recovery
status is logged under RG556WifiRecovery.

This is an automatic recovery mitigation. It does not correct the kernel driver
and cannot promise that every Wi-Fi failure will recover. A restart briefly
interrupts the Wi-Fi subsystem. It does not disable suspend or change radio power
settings. End-to-end recovery on a future naturally recurring failure remains to
be verified.

## Build and checks

Host policy tests, without Android or a device:

    mkdir -p build
    c++ -std=c++17 -Wall -Wextra -Werror wifi_recovery/monitor.cpp -o build/wifi-policy-test
    build/wifi-policy-test

Build the Android executable and module using an Android NDK toolchain:

    python3 wifi_recovery/build_module.py --cxx /path/to/NDK/toolchains/llvm/prebuilt/HOST/bin/aarch64-linux-android29-clang++

The package is build/wifi-recovery/rg556-wifi-recovery-experimental.zip. The module
accepts only rooted RG556 devices reporting GammaOS_Next_v1.2.

The monitor's --self-test checks the policy without changing Wi-Fi. Its --check
verifies device/root compatibility, new kernel-record access and the screen
property, and queries whether Wi-Fi is enabled. Its --dry-run monitors the real
signatures but logs rather than requesting recovery.

Initial validation: 13 policy checks passed on the host and on the RG556; root
kernel access, property access and the Wi-Fi status query passed on the device.
The manual Android recovery command restored the captured failure. These checks
do not replace testing a future automatic recovery and measuring standby impact.

The experimental module was installed on the test RG556 and its monitor started
successfully without rebooting or requesting another recovery on the healthy
connection. Startup skips old failure records. Automatic handling of the next
naturally recurring fault remains pending.

## Install and remove

Install the ZIP in Magisk and reboot. It is independent of the rotation module.
To stop the running monitor immediately:

    adb shell su -c 'sh /data/adb/modules/rg556_wifi_recovery/uninstall.sh'

Then disable or remove the module in Magisk and reboot. If a test instance was
started from modules_update before reboot, use that same modules_update path to
stop it. No framework files, saved networks or radio settings need restoration.

Device dumps and network details remain local under ignored research/ files.
