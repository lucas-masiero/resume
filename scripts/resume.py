#!/usr/bin/env python3
"""Validate Resumy input, render its PDF, and export a separate public front."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urljoin, urlsplit

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


def dependencies(root):
    config = read_json(root / "front.config.json")
    if config.get("schema_version") != 1 or set(config) != {"schema_version", "contacts", "resumy_path", "projects"}:
        raise ValueError("Unsupported front.config.json contract")
    allowed_contacts = {"email", "website", "linkedin", "phone"}
    if not isinstance(config["contacts"], list) or any(key not in allowed_contacts for key in config["contacts"]) or len(set(config["contacts"])) != len(config["contacts"]):
        raise ValueError("Invalid or repeated contact selection")
    source = (root / config["resumy_path"] / "src").resolve()
    if not (source / "resumy/schema.py").is_file():
        raise ValueError("Resumy source missing; set resumy_path in front.config.json")
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    from resumy.schema import load_data, validate
    from resumy.inline import format_inline
    data = load_data(root / "resume.json", "cv")
    if data["schema_version"] != 2:
        raise ValueError("This exporter expects Resumy CV schema version 2")
    return config, data, source, validate, format_inline


class InlineText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attributes):
        if tag == "link":
            self.current = {"label": "", "href": dict(attributes)["href"]}
        elif tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "link" and self.current:
            self.links.append(self.current)
            self.current = None

    def handle_data(self, data):
        self.parts.append(data)
        if self.current:
            self.current["label"] += data


def plain(value, formatter):
    parser = InlineText()
    parser.feed(formatter(value))
    return "".join(parser.parts), parser.links


def entry_front(entry, formatter):
    result = {"paragraphs": [], "bullets": [], "links": []}
    for key in ["title", "subtitle", "period", "location"]:
        if entry.get(key):
            result[key], links = plain(entry[key], formatter)
            result["links"].extend(links)
    for key in ["paragraphs", "bullets"]:
        for value in entry.get(key, []):
            text, links = plain(value, formatter)
            result[key].append(text)
            result["links"].extend(links)
    result["links"] = list({(link["href"], link["label"]): link for link in result["links"]}.values())
    return result


def https(value):
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or re.search(r"[\s\\]", value):
        raise ValueError(f"Expected HTTPS without credentials: {value}")
    return value


def local_file(base, relative):
    if not isinstance(relative, str) or not re.fullmatch(r"[\w.-]+(?:/[\w.-]+)*", relative) or any(part in {".", ".."} for part in relative.split("/")):
        raise ValueError(f"Unsafe local file: {relative}")
    candidate = base
    for part in relative.split("/"):
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError(f"Symlinks are unsupported: {relative}")
    if not candidate.is_file():
        raise ValueError(f"Missing local file: {relative}")
    return candidate


def catalog_assets(catalog, site_url):
    def asset(value):
        if value.startswith("assets/"):
            return https(urljoin(site_url.rstrip("/") + "/data/", value))
        return https(urljoin(site_url, value))
    tools = []
    for tool in read_json(catalog / "tools.json")["tools"]:
        tools.append({"id": tool["id"], "title": tool["title"], "description": tool["description"],
                      "programmingLanguage": tool["programmingLanguage"], "labels": tool["labels"],
                      "cover": asset(tool["cardPortrait"]), "links": tool["links"]})
    books = []
    for essay in read_json(catalog / "bookshelf.json")["essays"]:
        item = {key: essay[key] for key in ["id", "kind", "title", "description", "author", "edition", "media"] if essay.get(key)}
        item.update(labels=essay.get("labels", []), cover=asset(essay["cover"]), links=[],
                    licenses=[{**link, "href": asset(link["href"])} for link in essay["licenses"]])
        if essay.get("pdf"):
            item["pdfTeaser"] = asset(essay["pdf"])
        if essay.get("complete"):
            item["links"].append(essay["complete"])
        books.append(item)
    return tools, books


def prepare_front(root):
    config, data, source, validate, formatter = dependencies(root)
    person = data["person"]
    contacts = []
    for key in config["contacts"]:
        value = person.get(key)
        if not value:
            continue
        if key == "email":
            contact = {"kind": key, "label": value, "href": "mailto:" + value}
        elif key == "phone":
            contact = {"kind": key, "label": value, "href": "tel:" + re.sub(r"[^\d+]", "", value)}
        elif key == "website":
            contact = {"kind": key, "label": value["label"], "href": https(value["url"])}
        else:
            contact = {"kind": key, "label": "LinkedIn", "href": https(value)}
        contacts.append(contact)
    profile = data["sections"]["sidebar"].get("profile", {}).get("paragraphs", [])
    front_person = {"name": person["name"], "contacts": contacts}
    if person.get("headline"):
        front_person["headline"] = person["headline"]
    if profile:
        front_person["location"] = plain(profile[0], formatter)[0]
    copies = []
    if person.get("profile_pic"):
        photo = local_file(root, person["profile_pic"])
        front_person["portrait"] = "assets/" + photo.name
        copies.append((photo, front_person["portrait"]))
    side, main = data["sections"]["sidebar"], data["sections"]["main"]
    projects, ids, indices = [], set(), set()
    for selection in config["projects"]:
        allowed = {"id", "entry", "front", "site_catalog", "site_url", "repository"}
        if set(selection) - allowed or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", selection["id"]):
            raise ValueError("Invalid project selection")
        index = selection["entry"]
        if type(index) is not int or not 0 <= index < len(main["projects"]["entries"]) or selection["id"] in ids or index in indices:
            raise ValueError("Repeated or out-of-bounds project selection")
        ids.add(selection["id"]); indices.add(index)
        item = entry_front(main["projects"]["entries"][index], formatter)
        if not item.get("subtitle"):
            raise ValueError("Project entries need a subtitle describing the personal role/context")
        item.update(id=selection["id"], role=item["subtitle"])
        if selection.get("front"):
            directory = (root / selection["front"]).resolve()
            manifest = read_json(local_file(directory, "manifest.json"))
            if manifest.get("schemaVersion") != 1 or manifest.get("kind") != "project" or manifest.get("id") != selection["id"]:
                raise ValueError("Mismatched project presentation identity/version")
            if manifest["title"].casefold() not in item["title"].casefold():
                raise ValueError("Project selection no longer matches the resume entry; update its index")
            prefix = f"assets/projects/{selection['id']}/"
            for relative in ["manifest.json", "schema.json", "presentation.css", "LICENSE-SCHEMA"]:
                copies.append((local_file(directory, relative), prefix + relative))
            for file in (directory / "assets").rglob("*"):
                if file.is_symlink():
                    raise ValueError("Project asset symlinks are unsupported")
                if file.is_file():
                    relative = file.relative_to(directory).as_posix()
                    copies.append((local_file(directory, relative), prefix + relative))
            item["presentation"] = {"manifest": prefix + "manifest.json", "stylesheet": prefix + "presentation.css"}
        if selection.get("site_catalog"):
            item["tools"], item["books"] = catalog_assets((root / selection["site_catalog"]).resolve(), https(selection["site_url"]))
        if selection.get("repository"):
            expected = https(selection["repository"])
            if not any(link["href"] == expected for link in item["links"]):
                raise ValueError("Project selection no longer matches its repository; update entry indices/links")
        projects.append(item)
    if len(indices) != len(main["projects"]["entries"]):
        raise ValueError("Every resume project needs an explicit front selection")
    additional = []
    for column, sections in data["sections"].items():
        for key, section in sections.items():
            if key in {"profile", "skills", "education", "languages", "experience", "projects", "authored_books"}:
                continue
            additional.append({"id": key, "title": section.get("title", key), "column": column,
                               "paragraphs": [plain(value, formatter)[0] for value in section.get("paragraphs", [])],
                               "bullets": [plain(value, formatter)[0] for value in section.get("bullets", [])],
                               "entries": [entry_front(entry, formatter) for entry in section.get("entries", [])]})
    front = {"$schema": "./schema.json", "schema_version": 1, "kind": "resume", "person": front_person,
             "summary": [plain(value, formatter)[0] for value in profile[1:]],
             "education": [entry_front(entry, formatter) for entry in side["education"]["entries"]],
             "technicalSkills": {name: [plain(value, formatter)[0] for value in values] for name, values in side["skills"]["groups"].items()},
             "languages": side["languages"]["items"],
             "experience": [entry_front(entry, formatter) for entry in main["experience"]["entries"]],
             "projects": projects, "authoredBooks": [entry_front(entry, formatter) for entry in main.get("authored_books", {}).get("entries", [])], "additionalSections": additional,
             "sources": {"resume_sha256": hashlib.sha256((root / "resume.json").read_bytes()).hexdigest(), "project_ids": [item["id"] for item in projects]}}
    validate(front, read_json(root / "schemas/resume-front.schema.json"))
    return front, copies, source


def export_front(root, front, copies):
    stage = Path(tempfile.mkdtemp(prefix=".front-build-", dir=root))
    backup = None
    try:
        output = stage / "next"
        output.mkdir()
        for original, relative in copies:
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, destination)
        (output / "manifest.json").write_text(json.dumps(front, ensure_ascii=False, indent=2) + "\n")
        shutil.copyfile(root / "schemas/resume-front.schema.json", output / "schema.json")
        (output / "README.md").write_text("# Generated resume presentation\n\nGenerated by `python3 scripts/resume.py front` from ../resume.json and ../front.config.json.\nEdit those inputs, not this snapshot. All local references are relative to\nthis folder. Project bundles retain their own asset and license notices.\nThe CV PDF is included as assets/resume.pdf. Book URLs reference the publication owner; no book PDFs are copied here.\nThe phone is included only when explicitly selected in front.config.json.\n")
        destination = root / "front"
        if destination.exists():
            if destination.is_symlink() or not (destination / "manifest.json").is_file() or read_json(destination / "manifest.json").get("kind") != "resume":
                raise ValueError("Refusing to replace an unrecognized front directory")
            backup = stage / "previous"
            destination.rename(backup)
        try:
            output.rename(destination)
        except Exception:
            if backup:
                backup.rename(destination)
            raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def pdf_fingerprint(root):
    data = read_json(root / "resume.json")
    files = {"resume": root / "resume.json", "theme": root / "cfg.toml"}
    if data["person"].get("profile_pic"):
        files["portrait"] = local_file(root, data["person"]["profile_pic"])
    return {name: hashlib.sha256(file.read_bytes()).hexdigest() for name, file in files.items()}


def attach_pdf(root, front, copies):
    file = root / "output/pdf/lucas-masiero-resume.pdf"
    stamp = root / "output/pdf/resume-source.json"
    if not file.is_file() or not stamp.is_file() or read_json(stamp) != pdf_fingerprint(root):
        raise ValueError("CV PDF is missing or stale; run python3 scripts/resume.py build")
    if front["sources"]["resume_sha256"] != pdf_fingerprint(root)["resume"]:
        raise ValueError("Resume changed during export; run build again")
    if file.read_bytes()[:5] != b"%PDF-":
        raise ValueError("Invalid CV PDF")
    front["pdf"] = "assets/resume.pdf"
    front["sources"]["pdf_sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
    copies.append((file, front["pdf"]))


def render_pdf(root, source):
    before = pdf_fingerprint(root)
    source_json = (root / "resume.json").read_bytes()
    env = {**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run([sys.executable, "-m", "resumy", "cv", "--config", str(root / "cfg.toml"),
                    "--data", str(root / "resume.json"), "--output", str(root / "output/pdf/lucas-masiero-resume.pdf"), "--force"],
                   cwd=root, env=env, check=True)
    if pdf_fingerprint(root) != before or hashlib.sha256(source_json).hexdigest() != before["resume"]:
        raise ValueError("CV inputs changed during PDF rendering; run build again")
    (root / "output/pdf/lucas-masiero-resume.json").write_bytes(source_json)
    (root / "output/pdf/resume-source.json").write_text(json.dumps(before, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "pdf", "front", "build"])
    command = parser.parse_args().command
    if command in {"check", "pdf"}:
        _, data, source, _, _ = dependencies(ROOT)
        if command == "pdf":
            render_pdf(ROOT, source)
        print(f"CV valid: {len(data['sections']['main']['experience']['entries'])} experience entries, {len(data['sections']['main']['projects']['entries'])} projects.")
        return
    front, copies, source = prepare_front(ROOT)
    if command == "build":
        render_pdf(ROOT, source)
    attach_pdf(ROOT, front, copies)
    _, _, _, validate, _ = dependencies(ROOT)
    validate(front, read_json(ROOT / "schemas/resume-front.schema.json"))
    export_front(ROOT, front, copies)
    print(f"Front valid: {len(front['experience'])} experience entries, {len(front['projects'])} projects. Command: {command}.")



if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Resume: {error}", file=sys.stderr)
        raise SystemExit(1)
