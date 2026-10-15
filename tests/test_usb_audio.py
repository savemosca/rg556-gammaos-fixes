"""Exercise the installer and boot guard against synthetic, non-vendor policies."""
import hashlib
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from usb_audio.build_module import FILES, SOURCE, build_module

FIXTURE = '''<module name="primary" halVersion="2.0">
    <attachedDevices><item>Speaker</item></attachedDevices>
    <defaultOutputDevice>Speaker</defaultOutputDevice>
    <mixPorts>
        <mixPort name="primary output" role="source"/>
        <mixPort name="primary input" role="sink"/>
        <mixPort name="recognition input" role="sink"/>
    </mixPorts>
    <devicePorts>
        <devicePort tagName="Speaker" role="sink" type="AUDIO_DEVICE_OUT_SPEAKER"/>
        <devicePort tagName="Built-In Mic" role="source" type="AUDIO_DEVICE_IN_BUILTIN_MIC"/>
        <devicePort tagName="USB Device Out" type="AUDIO_DEVICE_OUT_USB_DEVICE" role="sink"/>
        <devicePort tagName="USB Headset Out" type="AUDIO_DEVICE_OUT_USB_HEADSET" role="sink"/>
        <devicePort tagName="USB Device In" type="AUDIO_DEVICE_IN_USB_DEVICE" role="source"/>
        <devicePort tagName="USB Headset In" type="AUDIO_DEVICE_IN_USB_HEADSET" role="source"/>
    </devicePorts>
    <routes>
        <route type="mix" sink="Speaker" sources="primary output"/>
        <route type="mix" sink="primary input" sources="Built-In Mic,USB Device In,USB Headset In"/>
        <route type="mix" sink="recognition input" sources="Built-In Mic,USB Headset In,USB Device In"/>
        <route type="mix" sink="USB Device Out"
               sources="primary output,compressed_offload,fast,voip_rx"/>
        <route type="mix" sink="USB Headset Out"
               sources="primary output,compressed_offload,fast,voip_rx"/>
    </routes>
</module>
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


class UsbAudioTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.module = self.root / "module with spaces"
        shutil.copytree(SOURCE / "module", self.module)
        self.original = self.root / "original.xml"
        self.original.write_text(FIXTURE)
        self.patched = subprocess.check_output([
            "awk", "-f", str(self.module / "patch.awk"), str(self.original)
        ])
        self.mounted = self.root / "mounted.xml"
        self.mounted.write_bytes(self.original.read_bytes())
        self.usb = self.root / "usb.xml"
        self.usb.write_text('<module name="usb"/>\n')
        compat = self.module / "compat.sh"
        data = compat.read_text()
        replacements = {
            "USB_AUDIO_ORIGINAL_SHA256": digest(self.original.read_bytes()),
            "USB_AUDIO_LEGACY_SHA256": digest(self.patched + b"\n"),
            "USB_AUDIO_PATCHED_SHA256": digest(self.patched),
            "USB_AUDIO_USB_POLICY_SHA256": digest(self.usb.read_bytes()),
        }
        lines = data.splitlines(keepends=True)
        compat.write_text("".join(
            f"{line.split('=', 1)[0]}={replacements[line.split('=', 1)[0]]}\n"
            if line.split('=', 1)[0] in replacements else line for line in lines
        ))
        self.env = {
            **os.environ, "MODPATH": str(self.module), "TMPDIR": str(self.root),
            "BOOTMODE": "true", "MAGISK_VER_CODE": "30600",
            "TEST_MODEL": "RG556", "TEST_VERSION": "GammaOS_Next_v1.2",
            "TEST_ORIGINAL": str(self.original), "TEST_MOUNTED": str(self.mounted),
            "TEST_USB": str(self.usb), "TEST_STAGE": "install",
        }
        self.wrapper = self.root / "harness.sh"
        self.wrapper.write_text('''
getprop() {
    case "$1" in
        ro.product.vendor.model) printf '%s\\n' "$TEST_MODEL" ;;
        ro.lineage.version) printf '%s\\n' "$TEST_VERSION" ;;
    esac
}
sha256sum() {
    case "$1" in
        /vendor/etc/primary_audio_policy_configuration.xml)
            if [ "$TEST_STAGE" = boot ]; then file=$TEST_ORIGINAL; else file=$TEST_MOUNTED; fi ;;
        /vendor/etc/usb_audio_policy_configuration.xml) file=$TEST_USB ;;
        *) file=$1 ;;
    esac
    python3 -c 'import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest()+"  "+sys.argv[1])' "$file"
}
magisk() {
    [ "$TEST_READ_FAILURE" != 1 ] || return 1
    [ "$1" = --denylist ] && [ "$2" = exec ] && [ "$3" = /system/bin/cat ] &&
    [ "$4" = /vendor/etc/primary_audio_policy_configuration.xml ] || return 2
    cat "$TEST_ORIGINAL"
}
abort() { printf '%s\\n' "$*" >&2; exit 1; }
ui_print() { printf '%s\\n' "$*"; }
set_perm_recursive() { :; }
set_perm() { :; }
log() { :; }
. "$TEST_SCRIPT"
''')

    def run_script(self, script="customize.sh", **environment):
        env = {**self.env, "TEST_SCRIPT": str(self.module / script), **environment}
        return subprocess.run(["sh", "-c", '. "$1"', str(self.module / script), str(self.wrapper)],
                              env=env, capture_output=True, text=True)

    @property
    def target(self):
        return self.module / "system/vendor/etc/primary_audio_policy_configuration.xml"

    def test_transformation_preserves_non_usb_topology(self):
        before, after = ET.fromstring(FIXTURE), ET.fromstring(self.patched)
        for name in ("attachedDevices", "defaultOutputDevice", "mixPorts"):
            self.assertEqual(ET.tostring(before.find(name)), ET.tostring(after.find(name)))
        self.assertEqual([p.get("tagName") for p in after.find("devicePorts")],
                         ["Speaker", "Built-In Mic"])
        self.assertEqual([(r.get("sink"), r.get("sources")) for r in after.find("routes")],
                         [("Speaker", "primary output"), ("primary input", "Built-In Mic"),
                          ("recognition input", "Built-In Mic")])

    def test_fresh_install_and_updates_from_both_versions(self):
        for mounted in (self.original.read_bytes(), self.patched + b"\n", self.patched):
            with self.subTest(mounted_hash=digest(mounted)):
                self.mounted.write_bytes(mounted)
                result = self.run_script()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.target.read_bytes(), self.patched)

    def test_unknown_current_policy_is_rejected_without_overlay(self):
        self.mounted.write_text("another module's policy")
        result = self.run_script()
        self.assertIn("Unknown active", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())

    def test_changed_original_is_not_hidden_by_recognized_overlay(self):
        self.mounted.write_bytes(self.patched)
        self.original.write_text("changed vendor firmware")
        result = self.run_script()
        self.assertIn("Unsupported original", result.stderr)
        self.assertFalse(self.target.exists())

    def test_device_version_magisk_recovery_and_namespace_guards(self):
        for overrides in ({"TEST_MODEL": "RG406H"}, {"TEST_VERSION": "GammaOS_Next_v1.4.4"},
                          {"MAGISK_VER_CODE": "23000"}, {"MAGISK_VER_CODE": "unknown"},
                          {"BOOTMODE": "false"}, {"TEST_READ_FAILURE": "1"}):
            with self.subTest(overrides=overrides):
                self.assertNotEqual(self.run_script(**overrides).returncode, 0)
                self.assertFalse(self.target.exists())

    def test_usb_policy_change_is_rejected(self):
        self.usb.write_text("different USB topology")
        self.assertIn("Unsupported USB", self.run_script().stderr)
        self.assertFalse(self.target.exists())

    def test_transform_output_is_independently_verified(self):
        with (self.module / "patch.awk").open("a") as stream:
            stream.write('\nEND { print "unexpected output" }\n')
        self.assertIn("Generated policy differs", self.run_script().stderr)

    def test_partial_input_is_rejected_by_transform(self):
        result = subprocess.run(["awk", "-f", str(self.module / "patch.awk")],
                                input=FIXTURE.replace('tagName="USB Headset In"', 'tagName="Other"'),
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

    def test_boot_guard_checks_before_mount_and_disables_on_changed_vendor(self):
        self.assertEqual(self.run_script().returncode, 0)
        self.original.write_text("updated firmware")
        result = self.run_script("post-fs-data.sh", TEST_STAGE="boot")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.module / "disable").exists())
        self.assertTrue((self.module / "skip_mount").exists())
        self.assertIn("Original primary", (self.module / "compatibility-error.txt").read_text())
        self.assertEqual(self.target.read_bytes(), self.patched)

    def test_boot_guard_accepts_only_matching_device_usb_and_payload(self):
        self.assertEqual(self.run_script().returncode, 0)
        result = self.run_script("post-fs-data.sh", TEST_STAGE="boot")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.module / "disable").exists())
        for change in ("device", "usb", "payload"):
            with self.subTest(change=change):
                for name in ("skip_mount", "disable", "compatibility-error.txt"):
                    (self.module / name).unlink(missing_ok=True)
                self.usb.write_text('<module name="usb"/>\n')
                self.target.write_bytes(self.patched)
                kwargs = {"TEST_MODEL": "other"} if change == "device" else {}
                if change == "usb": self.usb.write_text("changed")
                if change == "payload": self.target.write_bytes(b"corrupted")
                result = self.run_script("post-fs-data.sh", TEST_STAGE="boot", **kwargs)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((self.module / "skip_mount").exists())
                reason = (self.module / "compatibility-error.txt").read_text()
                self.assertIn({"device": "Device", "usb": "USB", "payload": "payload"}[change], reason)

    def test_package_is_repeatable_and_contains_only_owned_sources(self):
        (self.root / "output").mkdir()
        (self.root / "output/unexpected.xml").write_text("not packaged")
        package = build_module(self.root / "output")
        first = package.read_bytes()
        self.assertEqual(build_module(self.root / "output").read_bytes(), first)
        with zipfile.ZipFile(package) as archive:
            self.assertEqual(set(archive.namelist()), set(FILES) | {"LICENSE"})
            self.assertFalse(any(n.endswith(".xml") for n in archive.namelist()))
            for name in archive.namelist():
                self.assertEqual(archive.getinfo(name).date_time, (2026, 1, 1, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
