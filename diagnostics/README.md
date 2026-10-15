# Reproducing the Wi-Fi resume fault

This is a bounded diagnostic for a rooted RG556 with GammaOS Next 1.2 and its
5.4.233 vendor kernel. It attempts normal screen sleep/wake cycles and records
the driver calls leading to a fault. It does not inject a driver crash or force
the kernel to sleep around Android's suspend blockers.

The diagnostic uses the kernel's
[dynamic kprobe events](https://www.kernel.org/doc/html/v5.4/trace/kprobetrace.html)
in its own trace instance. Both driver variants present in the original Wi-Fi
module are covered. Calls to force-exit, deinitialization, card removal and
firmware assert functions record a stack trace. SDIO suspend/resume and the
power:suspend_resume tracepoint provide context. Probes observe calls; they do
not change arguments, memory or return values.

The native helper arms a CLOCK_BOOTTIME_ALARM timer before sending Android's
sleep key, then sends the wake key when that timer expires. The difference
between elapsed CLOCK_BOOTTIME and CLOCK_MONOTONIC measures time spent in system
suspend. A cycle with less than one second suspended is explicitly marked
invalid as a deep-suspend reproducer. One second is only a minimum validity
threshold, not enough to establish that a long standby bug is fixed.

## Build and run

Build with an Android NDK toolchain, for example:

    mkdir -p build/wifi-diagnostics
    /path/to/NDK/toolchains/llvm/prebuilt/HOST/bin/aarch64-linux-android29-clang++ \
      -std=c++17 -Wall -Wextra -Werror -O2 -static-libstdc++ \
      diagnostics/standby_cycle.cpp -o build/wifi-diagnostics/standby-cycle

Copy the executable and reproduce-wifi.sh into a fresh, private directory on the
device using root, with both files executable. The directory must not already
contain results/. Run the script detached with stdin, stdout and stderr
redirected; keep adb idle during sleep. The screen must initially be on and
Wi-Fi connected. The --check helper option only checks whether a wake alarm can
be armed; it does not turn off the screen.

- Default script mode: three cycles of 20, 30 and 60 seconds.
- --battery: wait up to approximately two minutes for USB power to disconnect,
  settle for five seconds, then run one 180-second cycle. Reconnect the cable
  after the screen has woken and another 15 seconds have passed.

For example, from a root device shell:

    nohup sh /data/local/tmp/PRIVATE_TEST_DIR/reproduce-wifi.sh --battery \
      </dev/null >/data/local/tmp/PRIVATE_TEST_DIR/runner.txt 2>&1 &

The first matching driver failure or lack of connection after wake stops further
cycles. A failure to set up required probes aborts the run. The script pauses
only the known recovery monitor if it is running, and restarts it on exit. Its
exit cleanup wakes the screen and removes only its own trace instance and
probes. It does not alter Wi-Fi settings or install a persistent service.

Results remain in results/ on the device. They include kernel records and Wi-Fi
status, which can contain private network information. Collect them into ignored
research/ storage; do not commit raw results. If a genuine failure is captured,
collect it before manually requesting Wi-Fi recovery. Restarting the monitor
does not replay historical failures.

## Initial trial, 15 October 2026

The executable compiled with Android NDK 27.1, and wake-alarm creation and arming
passed on the device. The tracing setup and automatic cleanup worked, and the
original recovery monitor was restarted at the end.

All three USB-connected cycles remained connected, but measured **zero time in
system suspend**, and the suspend-success counter did not advance. They are not
valid evidence about the reported deep-standby failure. Kernel records included
pending charger_manager_wakelock and dwc3-sprd wakeup sources. A battery-powered
trial is needed before interpreting a successful cycle as a reproduction test.

A successful trial without the intermittent fault does not establish a fix.
