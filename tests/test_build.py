import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("resume_builder", ROOT / "scripts/resume.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ResumeBuildTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix="resume-build-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in ["resume.json", "cfg.toml"]:
            shutil.copyfile(ROOT / name, root / name)
        shutil.copytree(ROOT / "assets", root / "assets")
        config = builder.read_json(ROOT / "build.config.json")
        config["resumyPath"] = str((ROOT / config["resumyPath"]).resolve())
        (root / "build.config.json").write_text(json.dumps(config))
        return root

    def test_native_cv_build_has_no_presentation_or_project_checkout_dependency(self):
        root = self.fixture()
        data, source = builder.dependencies(root)
        self.assertEqual(data["person"]["name"], "Lucas Masiero")
        self.assertTrue(source.is_dir())
        self.assertFalse((root / "front").exists())
        self.assertFalse((root / "Cohesian").exists())
        self.assertEqual(set(data["sections"]["main"]), {"experience", "projects", "authored_books"})

    def test_current_pdf_and_matching_json_are_reused_by_build(self):
        root = self.fixture()
        shutil.copytree(ROOT / "output/pdf", root / "output/pdf")
        before = (root / "output/pdf/lucas-masiero-resume.pdf").read_bytes()
        self.assertTrue(builder.output_is_current(root))
        with patch.object(builder, "ROOT", root), patch.object(sys, "argv", ["resume.py", "build"]), patch.object(builder, "render_pdf") as render:
            builder.main()
            render.assert_not_called()
        self.assertEqual((root / "output/pdf/lucas-masiero-resume.pdf").read_bytes(), before)
        (root / "cfg.toml").write_text((root / "cfg.toml").read_text() + "\n")
        self.assertFalse(builder.output_is_current(root))

    def test_render_saves_exact_input_and_fingerprints(self):
        root = self.fixture()
        _, source = builder.dependencies(root)
        original = (root / "resume.json").read_bytes()
        with patch.object(builder.subprocess, "run"):
            builder.render_pdf(root, source)
        self.assertEqual((root / "output/pdf/lucas-masiero-resume.json").read_bytes(), original)
        self.assertEqual(builder.read_json(root / "output/pdf/resume-source.json"), builder.pdf_fingerprint(root))
        self.assertEqual((root / "resume.json").read_bytes(), original)

    def test_input_changes_during_render_are_rejected(self):
        root = self.fixture()
        _, source = builder.dependencies(root)
        def change(*args, **kwargs):
            (root / "cfg.toml").write_text("changed")
        with patch.object(builder.subprocess, "run", side_effect=change), self.assertRaisesRegex(ValueError, "changed during"):
            builder.render_pdf(root, source)

    def test_duplicate_keys_and_unsafe_files_are_rejected(self):
        root = self.fixture()
        (root / "duplicate.json").write_text('{"x":1,"x":2}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            builder.read_json(root / "duplicate.json")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            builder.local_file(root, "../secret.png")
        (root / "photo.png").symlink_to(ROOT / "assets/profile.png")
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            builder.local_file(root, "photo.png")


if __name__ == "__main__":
    unittest.main()
