#!/usr/bin/env python3
"""Validate the native Resumy CV and build its PDF with a matching JSON snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def read_json(file):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{file}: duplicate key {key}")
            result[key] = value
        return result
    return json.loads(Path(file).read_text(), object_pairs_hook=unique)


def local_file(base, relative):
    if not isinstance(relative, str) or not re.fullmatch(r"[\w.-]+(?:/[\w.-]+)*", relative) or any(part in {".", ".."} for part in relative.split("/")):
        raise ValueError(f"Unsafe local file: {relative}")
    candidate = base
    for part in relative.split("/"):
        candidate /= part
        if candidate.is_symlink():
            raise ValueError(f"Symlinks are unsupported: {relative}")
    if not candidate.is_file():
        raise ValueError(f"Missing local file: {relative}")
    return candidate


def dependencies(root):
    config = read_json(root / "build.config.json")
    if set(config) != {"schemaVersion", "resumyPath"} or config["schemaVersion"] != 1:
        raise ValueError("Unsupported build.config.json contract")
    source = (root / config["resumyPath"] / "src").resolve()
    if not (source / "resumy/schema.py").is_file():
        raise ValueError("Resumy source missing; set resumyPath in build.config.json")
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    from resumy.schema import load_data
    data = load_data(root / "resume.json", "cv")
    if data["schema_version"] != 2:
        raise ValueError("This build expects Resumy CV schema version 2")
    return data, source


def pdf_fingerprint(root):
    data = read_json(root / "resume.json")
    files = {"resume": root / "resume.json", "theme": root / "cfg.toml"}
    if data["person"].get("profile_pic"):
        files["portrait"] = local_file(root, data["person"]["profile_pic"])
    return {name: hashlib.sha256(file.read_bytes()).hexdigest() for name, file in files.items()}


def output_is_current(root):
    output = root / "output/pdf"
    try:
        return ((output / "lucas-masiero-resume.pdf").read_bytes().startswith(b"%PDF-")
                and read_json(output / "resume-source.json") == pdf_fingerprint(root)
                and (output / "lucas-masiero-resume.json").read_bytes() == (root / "resume.json").read_bytes())
    except (OSError, ValueError):
        return False


def render_pdf(root, source):
    before = pdf_fingerprint(root)
    source_json = (root / "resume.json").read_bytes()
    output = root / "output/pdf"
    output.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run([sys.executable, "-m", "resumy", "cv", "--config", str(root / "cfg.toml"),
                    "--data", str(root / "resume.json"), "--output", str(output / "lucas-masiero-resume.pdf"), "--force"],
                   cwd=root, env=env, check=True)
    if pdf_fingerprint(root) != before or hashlib.sha256(source_json).hexdigest() != before["resume"]:
        raise ValueError("CV inputs changed during PDF rendering; run build again")
    (output / "lucas-masiero-resume.json").write_bytes(source_json)
    (output / "resume-source.json").write_text(json.dumps(before, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "pdf", "build"])
    command = parser.parse_args().command
    data, source = dependencies(ROOT)
    if command == "pdf" or (command == "build" and not output_is_current(ROOT)):
        render_pdf(ROOT, source)
    print(f"CV valid: {len(data['sections']['main']['experience']['entries'])} experience entries, {len(data['sections']['main']['projects']['entries'])} projects.")
    if command != "check":
        print("PDF and exact input JSON available in output/pdf/.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Resume: {error}", file=sys.stderr)
        raise SystemExit(1)
