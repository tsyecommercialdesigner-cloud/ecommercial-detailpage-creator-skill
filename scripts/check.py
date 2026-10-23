"""Read-only checks for this repository; Python 3.12+, locked PyYAML dependency.

This is a deliberately narrow project profile, not a general YAML/Markdown parser.
Exit 0 on success, 1 on invalid content. No network, writes or provider calls.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / ".agents/skills/ecommerce-detailpage-creator"


def read_metadata(path):
    text = path.read_text(encoding="utf-8")
    parts = text.split("\n---\n", 1)
    if not text.startswith("---\n") or len(parts) != 2:
        raise ValueError("Missing or unterminated frontmatter")
    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node):
        fields = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            if key in fields:
                raise ValueError("Duplicate frontmatter key")
            fields[key] = loader.construct_object(value_node)
        return fields

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        fields = yaml.load(parts[0][4:], Loader=UniqueLoader)
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML: {error}") from error
    if not isinstance(fields, dict):
        raise ValueError("Frontmatter must be a mapping")
    if set(fields) != {"name", "description"}:
        raise ValueError("Project frontmatter requires exactly name and description")
    name, description = fields["name"], fields["description"]
    if (not isinstance(name, str) or len(name) > 64
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)):
        raise ValueError("Invalid skill name")
    if name != path.parent.name:
        raise ValueError("Skill name differs from directory")
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
        raise ValueError("Invalid description")
    if not parts[1].strip():
        raise ValueError("Empty instructions")
    return fields


def anchors(text):
    found = set()
    for heading in re.findall(r"^#{1,6}\s+(.+)$", text, flags=re.M):
        found.add(re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-"))
    return found


def check_links(path, boundary):
    errors = []
    for link in re.findall(r"!?\[[^\]\n]*\]\(([^)\n]+)\)", path.read_text(encoding="utf-8")):
        target = urlsplit(link)
        if target.scheme in {"https", "http", "mailto"}:
            continue
        if target.scheme or target.netloc:
            errors.append(f"{path}: unsupported link: {link}")
            continue
        resolved = (path.parent / unquote(target.path)).resolve() if target.path else path.resolve()
        if not resolved.is_relative_to(boundary.resolve()):
            errors.append(f"{path}: link escapes boundary: {link}")
            continue
        if not resolved.is_file():
            errors.append(f"{path}: missing link target: {link}")
            continue
        # Windows exists() ignores case; match each actual filesystem component.
        lexical = path.parent / unquote(target.path) if target.path else path
        lexical = Path(lexical.absolute())
        for child in [lexical, *lexical.parents]:
            if child == boundary or child.parent == child:
                break
            if child.name in {".", ".."}:
                continue
            if child.parent.exists() and child.name not in {p.name for p in child.parent.iterdir()}:
                errors.append(f"{path}: link case mismatch: {link}")
                break
        if target.fragment and unquote(target.fragment) not in anchors(resolved.read_text(encoding="utf-8")):
            errors.append(f"{path}: missing heading: {link}")
    return errors


def check_cases(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("rubric_version") != "1" or data.get("runs_per_case") != 3:
        raise ValueError("Unexpected rubric or repetition count")
    cases = data.get("cases", [])
    ids = set()
    if not cases:
        raise ValueError("No evaluation cases")
    for case in cases:
        identifier = case.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError("Missing or duplicate case id")
        ids.add(identifier)
        if case.get("expected_selection") not in {"yes", "no", "clarify"}:
            raise ValueError(f"{identifier}: invalid selection")
        for field in ("request", "fixtures"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f"{identifier}: missing {field}")
        for field in ("expected", "critical"):
            if not isinstance(case.get(field), list) or not case[field] or any(
                not isinstance(item, str) or not item.strip() for item in case[field]
            ):
                raise ValueError(f"{identifier}: invalid {field}")
    return len(cases)


def main():
    try:
        metadata = read_metadata(SKILL / "SKILL.md")
        errors = []
        files = [*SKILL.rglob("*.md"), *REPO.joinpath("docs").glob("*.md"),
                 *REPO.joinpath("evals").glob("*.md"), REPO / "README.md"]
        for path in files:
            errors.extend(check_links(path, SKILL if path.is_relative_to(SKILL) else REPO))
        count = check_cases(REPO / "evals/cases.json")
        if errors:
            raise ValueError("\n".join(errors))
        print(f"PASS: {metadata['name']}; {len(files)} Markdown files; {count} evaluation definitions")
        print("Scope: structure, local links, evaluation data only; no model or image execution")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
