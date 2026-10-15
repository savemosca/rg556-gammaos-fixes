// SPDX-License-Identifier: Apache-2.0
// Recover only the observed SC2355 driver failure; do not poll the radio.
#include <cstdint>
#include <cstdio>
#include <cstring>

struct Policy {
    uint64_t hif_at = 0, scan_at = 0, last_attempt = 0, window_start = 0;
    unsigned attempts = 0;
    bool pending = false;

    void observe(const char* message, uint64_t now) {
        if (std::strstr(message, "sprd-wlan:") && std::strstr(message, "hif->exit"))
            hif_at = now;
        if (std::strstr(message, "wlan0:") &&
            std::strstr(message, "sc2355_scan failed (-12)"))
            scan_at = now;
        if (hif_at && scan_at &&
            (hif_at > scan_at ? hif_at - scan_at : scan_at - hif_at) <= 5000)
            pending = true;
        // A fresh driver interface invalidates any previously paired failure.
        if (std::strstr(message, "sprd-wlan:") && std::strstr(message, "Supported Feature:"))
            clear_failure();
    }

    void clear_failure() { pending = false; hif_at = scan_at = 0; }

    bool rate_limited(uint64_t now) const {
        return (last_attempt && now - last_attempt < 180000) ||
            (window_start && now - window_start < 3600000 && attempts >= 2);
    }

    bool request(uint64_t now, bool awake, bool wifi_enabled) {
        if (!pending || !awake) return false;
        clear_failure();
        if (!wifi_enabled) return false;
        if (last_attempt && now - last_attempt < 180000) return false;
        if (!window_start || now - window_start >= 3600000) {
            window_start = now;
            attempts = 0;
        }
        if (attempts >= 2) return false;
        last_attempt = now;
        ++attempts;
        return true;
    }
};

static int self_test() {
    const char* hif = "sprd-wlan: sc2355_tx_get_msg can not get msg: hif->exit";
    const char* scan = "wlan0: sc2355_scan failed (-12)";
    unsigned checks = 0;
    auto check = [&](bool value) { ++checks; if (!value) std::fprintf(stderr, "failed check %u\n", checks); return value; };
    Policy p;
    if (!check(!p.request(1000, true, true))) return 1;
    p.observe("wlan0: normal disconnect", 1100);
    if (!check(!p.request(1100, true, true))) return 1;
    p.observe(scan, 1200);
    if (!check(!p.request(1200, true, true))) return 1;
    p.observe(hif, 1300);
    if (!check(!p.request(1300, false, true) && p.pending)) return 1;
    if (!check(!p.request(1400, true, false) && !p.pending)) return 1;
    p.observe(hif, 2000); p.observe(scan, 2001);
    if (!check(p.request(2100, true, true))) return 1;
    if (!check(!p.request(2101, true, true))) return 1;
    p.observe(hif, 2200); p.observe(scan, 2201);
    if (!check(!p.request(2202, true, true))) return 1;
    p.observe(hif, 200000); p.observe(scan, 200001);
    if (!check(p.request(200002, true, true))) return 1;
    p.observe(hif, 400000); p.observe(scan, 400001);
    if (!check(!p.request(400002, true, true))) return 1;
    p.observe(hif, 3700000); p.observe(scan, 3700001);
    if (!check(p.request(3700002, true, true))) return 1;
    Policy stale;
    stale.observe(hif, 1000); stale.observe(scan, 7000);
    if (!check(!stale.request(7001, true, true))) return 1;
    Policy reset;
    reset.observe(hif, 1000); reset.observe(scan, 1001);
    reset.observe("sprd-wlan: Supported Feature:0x401001f", 1002);
    if (!check(!reset.request(1003, true, true))) return 1;
    std::printf("Passed %u Wi-Fi recovery policy checks\n", checks);
    return 0;
}

#ifdef __ANDROID__
#include <android/log.h>
#include <cerrno>
#include <cstdlib>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <sys/system_properties.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static int screen_pipe[2];
static const prop_info* screen_property;
static bool property_equals(const char* key, const char* expected) {
    char value[PROP_VALUE_MAX] = {};
    __system_property_get(key, value);
    return std::strcmp(value, expected) == 0;
}
static uint64_t now_ms() {
    timespec t{};
    clock_gettime(CLOCK_BOOTTIME, &t);
    return uint64_t(t.tv_sec) * 1000 + t.tv_nsec / 1000000;
}
static void log(const char* text) {
    __android_log_write(ANDROID_LOG_INFO, "RG556WifiRecovery", text);
}
static bool wifi_is_enabled() {
    FILE* stream = popen("/system/bin/timeout 5 /system/bin/cmd wifi status", "r");
    if (!stream) return false;
    char line[2048];
    bool enabled = false;
    while (std::fgets(line, sizeof(line), stream))
        if (std::strcmp(line, "Wifi is enabled\n") == 0) enabled = true;
    const int result = pclose(stream);
    return result == 0 && enabled;
}
static void* watch_screen(void*) {
    uint32_t serial = 0;
    __system_property_read_callback(screen_property,
        [](void* cookie, const char*, const char*, uint32_t value) {
            *static_cast<uint32_t*>(cookie) = value;
        }, &serial);
    const char initial_tick = 1;
    const ssize_t initial_write = write(screen_pipe[1], &initial_tick, 1);
    (void)initial_write;
    while (__system_property_wait(screen_property, serial, &serial, nullptr)) {
        const char tick = 1;
        // The pipe is nonblocking; an existing notification is sufficient.
        const ssize_t ignored = write(screen_pipe[1], &tick, 1);
        (void)ignored;
    }
    return nullptr;
}
static bool request_recovery() {
    const pid_t child = fork();
    if (child == 0) {
        execl("/system/bin/timeout", "timeout", "10", "/system/bin/cmd",
              "wifi", "trigger-recovery", static_cast<char*>(nullptr));
        _exit(127);
    }
    if (child < 0) return false;
    int status = 0;
    pid_t result;
    do { result = waitpid(child, &status, 0); } while (result < 0 && errno == EINTR);
    return result == child && WIFEXITED(status) && WEXITSTATUS(status) == 0;
}

int main(int argc, char** argv) {
    if (argc == 2 && std::strcmp(argv[1], "--self-test") == 0) return self_test();
    const bool check_only = argc == 2 && std::strcmp(argv[1], "--check") == 0;
    const bool dry_run = argc == 2 && std::strcmp(argv[1], "--dry-run") == 0;
    if (argc > 1 && !check_only && !dry_run) return 2;
    if (geteuid() != 0 || !property_equals("ro.product.vendor.model", "RG556") ||
        !property_equals("ro.lineage.version", "GammaOS_Next_v1.2")) {
        std::fprintf(stderr, "Requires root on RG556 GammaOS Next 1.2\n");
        return 2;
    }
    const int kernel = open("/dev/kmsg", O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (kernel < 0 || lseek(kernel, 0, SEEK_END) < 0) {
        std::fprintf(stderr, "Cannot follow new kernel records: %s\n", std::strerror(errno));
        return 3;
    }
    screen_property = __system_property_find("sys.screen.state");
    if (!screen_property) return 4;
    if (check_only) {
        std::printf("Kernel access: OK; screen property: OK; Wi-Fi enabled: %s\n",
                    wifi_is_enabled() ? "yes" : "no or query unavailable");
        close(kernel);
        return 0;
    }
    if (pipe2(screen_pipe, O_NONBLOCK | O_CLOEXEC) < 0) return 5;
    pthread_t watcher;
    if (pthread_create(&watcher, nullptr, watch_screen, nullptr) != 0) return 6;
    pthread_detach(watcher);
    Policy policy;
    pollfd fds[] = {{kernel, POLLIN, 0}, {screen_pipe[0], POLLIN, 0}};
    log(dry_run ? "Monitoring new driver failures (dry run)" : "Monitoring new driver failures");
    for (;;) {
        const int ready = poll(fds, 2, -1);  // no periodic polling or wakelock
        if (ready < 0) { if (errno == EINTR) continue; return 7; }
        if (fds[0].revents & (POLLHUP | POLLNVAL)) return 8;
        if (fds[0].revents & (POLLIN | POLLERR)) {
            char buffer[65536];
            ssize_t count;
            while ((count = read(kernel, buffer, sizeof(buffer) - 1)) > 0) {
                buffer[count] = '\0';
                const char* message = std::strchr(buffer, ';');
                policy.observe(message ? message + 1 : buffer, now_ms());
            }
            if (count < 0 && errno == EPIPE) {
                policy.clear_failure();
                if (lseek(kernel, 0, SEEK_END) < 0) return 9;
            } else if (count < 0 && errno != EAGAIN && errno != EINTR) return 10;
        }
        if (fds[1].revents & POLLIN) {
            char buffer[64];
            while (read(screen_pipe[0], buffer, sizeof(buffer)) > 0) {}
        }
        if (policy.pending && property_equals("sys.screen.state", "on")) {
            if (policy.rate_limited(now_ms())) { policy.clear_failure(); continue; }
            if (policy.request(now_ms(), true, wifi_is_enabled())) {
                if (dry_run) log("Would request Wi-Fi recovery for paired SC2355 errors");
                else log(request_recovery() ? "Requested Wi-Fi subsystem recovery" : "Wi-Fi recovery command failed");
            }
        }
    }
}
#else
int main() { return self_test(); }
#endif
