import pathlib
import tempfile
import unittest
from unittest import mock

from build_rotation_fix import build_module, patch_dex
from verify_rotation_patch import verify_prefix


class RotationPatchTests(unittest.TestCase):
    def test_valid_rotations_and_invalid_readings_follow_actual_dex_branches(self):
        self.assertEqual(verify_prefix(), 36)

    def test_unsupported_firmware_is_rejected_before_writing_or_running_tools(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            original = root / "unsupported.jar"
            original.write_bytes(b"not the verified firmware")
            output = root / "output"
            with mock.patch("build_rotation_fix.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    build_module(original, output, "unused-zipalign")
                run.assert_not_called()
            self.assertFalse(output.exists())

    def test_unexpected_dex_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unexpected framework"):
            patch_dex(b"dex\n035\0" + bytes(120))


if __name__ == "__main__":
    unittest.main()
