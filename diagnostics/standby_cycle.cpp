// SPDX-License-Identifier: Apache-2.0
// One bounded screen sleep/wake cycle, with a kernel wake alarm.
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <sys/timerfd.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static long long milliseconds(clockid_t clock) {
    timespec value{};
    if (clock_gettime(clock, &value) != 0) return -1;
    return static_cast<long long>(value.tv_sec) * 1000 + value.tv_nsec / 1000000;
}

static bool key(const char* code) {
    pid_t child = fork();
    if (child == 0) {
        execl("/system/bin/input", "input", "keyevent", code, static_cast<char*>(nullptr));
        _exit(127);
    }
    if (child < 0) return false;
    int status = 0;
    pid_t result;
    do { result = waitpid(child, &status, 0); } while (result < 0 && errno == EINTR);
    return result == child && WIFEXITED(status) && WEXITSTATUS(status) == 0;
}

int main(int argc, char** argv) {
    if (argc == 2 && std::strcmp(argv[1], "--capture-kernel") == 0) {
        const int kernel = open("/dev/kmsg", O_RDONLY | O_CLOEXEC);
        if (kernel < 0 || lseek(kernel, 0, SEEK_END) < 0) return 7;
        char buffer[65536];
        size_t total = 0;
        while (total < 32 * 1024 * 1024) {
            const ssize_t count = read(kernel, buffer, sizeof(buffer));
            if (count < 0 && errno == EINTR) continue;
            if (count < 0 && errno == EPIPE) {
                const char lost[] = "RG556_CAPTURE: kernel records lost\n";
                if (write(STDOUT_FILENO, lost, sizeof(lost) - 1) < 0) return 8;
                continue;
            }
            if (count <= 0) return 8;
            ssize_t offset = 0;
            while (offset < count) {
                const ssize_t written = write(STDOUT_FILENO, buffer + offset, count - offset);
                if (written < 0 && errno == EINTR) continue;
                if (written <= 0) return 8;
                offset += written;
            }
            total += static_cast<size_t>(count);
        }
        return 9;
    }
    const bool check = argc == 2 && std::strcmp(argv[1], "--check") == 0;
    char* end = nullptr;
    const long seconds = argc == 2 && !check ? std::strtol(argv[1], &end, 10) : 0;
    if (!check && (argc != 2 || !end || *end || seconds < 10 || seconds > 600)) {
        std::fprintf(stderr, "Usage: standby-cycle --check | SECONDS (10..600)\n");
        return 2;
    }
    const int alarm = timerfd_create(CLOCK_BOOTTIME_ALARM, TFD_CLOEXEC);
    if (alarm < 0) { std::perror("timerfd_create wake alarm"); return 3; }
    itimerspec timer{};
    timer.it_value.tv_sec = check ? 1 : seconds;
    if (timerfd_settime(alarm, 0, &timer, nullptr) != 0) {
        std::perror("timerfd_settime wake alarm"); close(alarm); return 4;
    }
    if (check) {
        close(alarm); // Closing cancels the check alarm; the screen is untouched.
        std::puts("Wake alarm can be created and armed");
        return 0;
    }
    const long long boot_before = milliseconds(CLOCK_BOOTTIME);
    const long long mono_before = milliseconds(CLOCK_MONOTONIC);
    if (!key("223")) { key("224"); close(alarm); return 5; }
    unsigned long long expirations = 0;
    ssize_t count;
    do { count = read(alarm, &expirations, sizeof(expirations)); }
    while (count < 0 && errno == EINTR);
    const long long elapsed = milliseconds(CLOCK_BOOTTIME) - boot_before;
    const long long awake = milliseconds(CLOCK_MONOTONIC) - mono_before;
    const bool woke = key("224");
    close(alarm);
    std::printf("requested_seconds=%ld elapsed_ms=%lld suspended_ms=%lld alarm_ok=%d wake_ok=%d\n",
                seconds, elapsed, elapsed - awake,
                count == static_cast<ssize_t>(sizeof(expirations)), woke);
    return count == static_cast<ssize_t>(sizeof(expirations)) && woke ? 0 : 6;
}
