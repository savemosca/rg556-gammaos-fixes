"""Execute the patched DEX prefix and optionally verify a generated module."""
import argparse
import hashlib
import pathlib
import struct
import zipfile
import zlib

from build_rotation_fix import EXPECTED_ORIGINAL_SHA256, PATCHED_PREFIX, PATCH_OFFSET, patch_dex


def execute(words, raw, offset):
    regs = {0: None, 1: None, 5: None, 10: "outer", 11: [float(raw)]}
    pc, result = 0, None
    for _ in range(30):
        if pc == 0xF1:
            return None  # existing return-void
        if pc == 0x16:
            return regs[5]  # remainder of existing method
        word = words[pc]
        op, a, b = word & 255, (word >> 8) & 15, word >> 12
        if op == 0x54:  # iget-object: event.values or judge.this$0
            regs[a] = regs[b]
            pc += 2
        elif op == 0x12:
            regs[a] = b if b < 8 else b - 16
            pc += 1
        elif op == 0x44:
            aa = word >> 8
            bb, cc = words[pc + 1] & 255, words[pc + 1] >> 8
            regs[aa] = regs[bb][regs[cc]]
            pc += 2
        elif op == 0x87:
            regs[a] = int(regs[b])
            pc += 1
        elif op == 0x36:
            pc += words[pc + 1] if regs[a] > regs[b] else 2
        elif op == 0x3A:
            pc += words[pc + 1] if regs[word >> 8] < 0 else 2
        elif op == 0x71:  # verified accessor mSysuiAccelOffset
            result = offset
            pc += 3
        elif op == 0x0A:
            regs[word >> 8] = result
            pc += 1
        elif op == 0xB0:
            regs[a] += regs[b]
            pc += 1
        elif op == 0xDD:
            regs[word >> 8] = regs[words[pc + 1] & 255] & (words[pc + 1] >> 8)
            pc += 2
        elif op == 0:
            pc += 1
        else:
            raise ValueError(f"Unexpected opcode {op:x} at {pc:x}")
    raise ValueError("Branch failed to terminate")


def verify_prefix(prefix=PATCHED_PREFIX):
    words = struct.unpack("<22H", prefix)
    checks = 0
    for offset in range(4):
        for raw in [-2147483648, -2, -1, 0, 1, 2, 3, 4, 2147483647]:
            expected = None if raw < 0 or raw > 3 else (raw + offset) % 4
            if execute(words, raw, offset) != expected:
                raise ValueError(f"Incorrect branch result for raw={raw}, offset={offset}")
            checks += 1
    return checks


def verify_module(original_path, module_path):
    if hashlib.sha256(original_path.read_bytes()).hexdigest() != EXPECTED_ORIGINAL_SHA256:
        raise ValueError("Unsupported original framework")
    with zipfile.ZipFile(original_path) as original, zipfile.ZipFile(module_path) as patched:
        if original.namelist() != patched.namelist():
            raise ValueError("JAR entries differ")
        for name in original.namelist():
            expected = patch_dex(original.read(name)) if name == "classes3.dex" else original.read(name)
            if patched.read(name) != expected:
                raise ValueError(f"Unexpected JAR change: {name}")
        data = patched.read("classes3.dex")
    if data[12:32] != hashlib.sha1(data[32:]).digest():
        raise ValueError("Invalid DEX SHA-1")
    if struct.unpack_from("<I", data, 8)[0] != zlib.adler32(data[12:]) & 0xFFFFFFFF:
        raise ValueError("Invalid DEX Adler-32")
    return verify_prefix(data[PATCH_OFFSET:PATCH_OFFSET + len(PATCHED_PREFIX)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="Check control flow without firmware files")
    parser.add_argument("--original", type=pathlib.Path, default=pathlib.Path("research/services.jar"))
    parser.add_argument("--module-jar", type=pathlib.Path, default=pathlib.Path("build/rotation-module/system/framework/services.jar"))
    args = parser.parse_args()
    checks = verify_prefix() if args.self_test else verify_module(args.original, args.module_jar)
    print(f"Passed {checks} DEX control-flow checks" + (
        "." if args.self_test else "; exact JAR changes and DEX checksums verified."
    ))


if __name__ == "__main__":
    main()
