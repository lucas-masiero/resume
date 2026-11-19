import importlib.util
import hashlib
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


class ResumeFrontTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix="resume-front-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in ["resume.json", "front.config.json", "cfg.toml"]:
            shutil.copyfile(ROOT / name, root / name)
        for name in ["assets", "schemas"]:
            shutil.copytree(ROOT / name, root / name)
        config = builder.read_json(root / "front.config.json")
        config["resumy_path"] = str((ROOT / config["resumy_path"]).resolve())
        for project in config["projects"]:
            for key in ["front", "site_catalog"]:
                if key in project:
                    project[key] = str((ROOT / project[key]).resolve())
        (root / "front.config.json").write_text(json.dumps(config))
        return root, config

    def test_cv_and_front_are_separate_contracts_and_preserve_project_credit(self):
        before = (ROOT / "resume.json").read_bytes()
        front, copies, _ = builder.prepare_front(ROOT)
        raw = builder.read_json(ROOT / "resume.json")
        self.assertEqual((ROOT / "resume.json").read_bytes(), before)
        self.assertEqual(front["kind"], "resume")
        self.assertEqual(front["person"]["name"], raw["person"]["name"])
        self.assertEqual(len(front["experience"]), len(raw["sections"]["main"]["experience"]["entries"]))
        self.assertEqual({p["id"] for p in front["projects"]}, {"cohesian", "home-solutions", "leetcode"})
        project = next(p for p in front["projects"] if p["id"] == "cohesian")
        self.assertIn("author", project["role"])
        self.assertTrue(project["tools"])
        self.assertTrue(project["books"])
        self.assertTrue(any(relative.endswith("licenses/NOTICE.txt") for _, relative in copies))
        self.assertFalse(any(relative.endswith(".pdf") for _, relative in copies))
        for book in project["books"]:
            self.assertTrue(book["pdfTeaser"].startswith("https://"))

    def test_phone_is_excluded_from_front_until_selected(self):
        root, config = self.fixture()
        front, _, _ = builder.prepare_front(root)
        self.assertNotIn("phone", {c["kind"] for c in front["person"]["contacts"]})
        self.assertIn("phone", builder.read_json(root / "resume.json")["person"])
        config["contacts"].append("phone")
        (root / "front.config.json").write_text(json.dumps(config))
        front, _, _ = builder.prepare_front(root)
        self.assertIn("phone", {c["kind"] for c in front["person"]["contacts"]})

    def test_failed_validation_keeps_existing_export_and_reordered_projects_are_detected(self):
        root, _ = self.fixture()
        front, copies, _ = builder.prepare_front(root)
        builder.export_front(root, front, copies)
        before = (root / "front/manifest.json").read_bytes()
        data = builder.read_json(root / "resume.json")
        data["sections"]["main"]["projects"]["entries"].reverse()
        (root / "resume.json").write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            builder.prepare_front(root)
        self.assertEqual((root / "front/manifest.json").read_bytes(), before)

    def test_pdf_command_does_not_require_project_sources(self):
        root, config = self.fixture()
        config["projects"][0]["front"] = "does-not-exist"
        config["projects"][0]["site_catalog"] = "does-not-exist"
        (root / "front.config.json").write_text(json.dumps(config))
        with patch.object(builder, "ROOT", root), patch.object(sys, "argv", ["resume.py", "pdf"]), patch.object(builder, "render_pdf") as render:
            builder.main()
            render.assert_called_once()

    def test_generated_assets_are_portable_and_do_not_include_source_paths(self):
        root, _ = self.fixture()
        front, copies, _ = builder.prepare_front(root)
        builder.export_front(root, front, copies)
        exported = (root / "front/manifest.json").read_text()
        self.assertNotIn(str(root), exported)
        self.assertNotIn(str(ROOT), exported)
        self.assertNotIn("resumy_path", exported)
        for original, relative in copies:
            self.assertEqual(original.read_bytes(), (root / "front" / relative).read_bytes())
        portrait = root / "front" / front["person"]["portrait"]
        self.assertTrue(portrait.is_file())

    def test_duplicate_keys_and_unsafe_or_symlinked_files_are_rejected(self):
        root, _ = self.fixture()
        file = root / "duplicate.json"
        file.write_text('{"key":1,"key":2}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            builder.read_json(file)
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            builder.local_file(root, "../secret.png")
        (root / "photo.png").symlink_to(ROOT / "assets/profile.png")
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            builder.local_file(root, "photo.png")

    def test_authored_books_replace_retired_architecture_sections(self):
        raw = builder.read_json(ROOT / "resume.json")
        self.assertNotIn("architecture_studies", raw["sections"]["main"])
        self.assertNotIn("earlier_research", raw["sections"]["main"])
        self.assertNotIn("other_system_designs", raw["sections"]["sidebar"])
        front, _, _ = builder.prepare_front(ROOT)
        self.assertEqual(len(front["authoredBooks"]), 2)
        self.assertIn("Golang", front["authoredBooks"][0]["title"])
        self.assertIn("System Architecture", front["authoredBooks"][1]["title"])
        text = " ".join(front["authoredBooks"][1]["bullets"])
        self.assertIn("planned", text)
        self.assertIn("Modules Implementation", text)
        self.assertIn("Infrastructure", text)

    def test_exported_pdf_is_bound_to_the_current_cv_and_theme(self):
        root, _ = self.fixture()
        output = root / "output/pdf"
        output.mkdir(parents=True)
        pdf = output / "lucas-masiero-resume.pdf"
        pdf.write_bytes(b"%PDF-1.7\nfixture")
        (output / "resume-source.json").write_text(json.dumps(builder.pdf_fingerprint(root)))
        front, copies, _ = builder.prepare_front(root)
        builder.attach_pdf(root, front, copies)
        self.assertEqual(front["pdf"], "assets/resume.pdf")
        self.assertEqual(front["sources"]["pdf_sha256"], hashlib.sha256(pdf.read_bytes()).hexdigest())
        self.assertEqual([relative for _, relative in copies if relative.endswith(".pdf")], ["assets/resume.pdf"])
        (root / "cfg.toml").write_text((root / "cfg.toml").read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "missing or stale"):
            builder.attach_pdf(root, front, copies)

    def test_pdf_build_saves_the_exact_input_next_to_the_pdf(self):
        root, _ = self.fixture()
        _, _, source, _, _ = builder.dependencies(root)
        output = root / "output/pdf"
        output.mkdir(parents=True)
        original = (root / "resume.json").read_bytes()
        with patch.object(builder.subprocess, "run"):
            builder.render_pdf(root, source)
        self.assertEqual((output / "lucas-masiero-resume.json").read_bytes(), original)
        self.assertEqual(builder.read_json(output / "resume-source.json"), builder.pdf_fingerprint(root))
        self.assertEqual((root / "resume.json").read_bytes(), original)

    def test_roles_follow_the_cv_and_repository_links_guard_project_identity(self):
        root, _ = self.fixture()
        raw = builder.read_json(root / "resume.json")
        raw["sections"]["main"]["projects"]["entries"][0]["subtitle"] = "Example author role"
        (root / "resume.json").write_text(json.dumps(raw))
        front, _, _ = builder.prepare_front(root)
        self.assertEqual(front["projects"][0]["role"], "Example author role")
        entries = raw["sections"]["main"]["projects"]["entries"]
        entries[1], entries[2] = entries[2], entries[1]
        (root / "resume.json").write_text(json.dumps(raw))
        with self.assertRaisesRegex(ValueError, "no longer matches its repository"):
            builder.prepare_front(root)


if __name__ == "__main__":
    unittest.main()
