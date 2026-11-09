import hashlib
import re
import uuid
from pathlib import Path


# Fallback for a caller that has not read hugo.toml yet.
# The skew shortcode prints the release without the leading v.
DOCS_VERSION = "1.37"


def docs_version(hugo_toml):
    match = re.search(r'^version = "v([^"]+)"', hugo_toml, re.MULTILINE)
    if match is None:
        raise ValueError("hugo.toml has no version")
    return match.group(1)


def docs_releases(hugo_toml):
    """Return one record for each published release in hugo.toml."""
    latest_match = re.search(r'^latest = "v([^"]+)"', hugo_toml, re.MULTILINE)
    if latest_match is None:
        raise ValueError("hugo.toml has no latest")
    latest = latest_match.group(1)
    releases = []
    blocks = re.split(r'^\[\[params\.versions\]\]\s*', hugo_toml, flags=re.MULTILINE)
    for block in blocks[1:]:
        block = re.split(r'^\[', block, maxsplit=1, flags=re.MULTILINE)[0]
        version = re.search(r'^version = "v([^"]+)"', block, re.MULTILINE)
        branch = re.search(r'^docsbranch = "([^"]+)"', block, re.MULTILINE)
        url = re.search(r'^url = "([^"]+)"', block, re.MULTILINE)
        if version is None or branch is None or url is None:
            raise ValueError("hugo.toml version entry is incomplete")
        number = version.group(1)
        releases.append(
            {
                "version": number,
                "branch": branch.group(1),
                "url": url.group(1),
                "latest": number == latest,
            }
        )
    if not releases:
        raise ValueError("hugo.toml has no versions")
    return releases


def release_for(hugo_toml):
    """Return the published release this checkout documents."""
    version = docs_version(hugo_toml)
    for release in docs_releases(hugo_toml):
        if release["version"] == version:
            return release
    raise ValueError("hugo.toml version is not in the versions table")


def page_url(release_url, path):
    """Return the public page link for one docs file."""
    prefix = "content/en/"
    if not path.startswith(prefix):
        raise ValueError("docs path is outside content/en")
    relative = path[len(prefix):]
    if relative.endswith("_index.md"):
        relative = relative[: -len("_index.md")]
    elif relative.endswith(".md"):
        relative = relative[: -len(".md")] + "/"
    else:
        raise ValueError("docs path is not a markdown page")
    return release_url.rstrip("/") + "/" + relative


def point_id(source, version, path, heading, position):
    """Return a stable id for one section of one docs release."""
    raw = "\0".join((source, version, path, heading, str(position)))
    return hashlib.sha256(raw.encode()).hexdigest()


def point_uuid(section_id):
    """Return the Qdrant point id for one section hash."""
    return str(uuid.UUID(hex=section_id[:32]))


def sections_of(lines, version, path, release_url, source, license):
    """Yield each section of a page with its stable id."""
    sections = chunk_page(
        lines,
        version=version,
        path=path,
        release_url=release_url,
        source=source,
        license=license,
    )
    for position, section in enumerate(sections):
        section["id"] = point_id(
            source, version, path, section["heading"], position
        )
        yield section


def sections_under(repo, version, release_url, source, license):
    """Yield every section under content/en/docs, in path order."""
    repo = Path(repo)
    docs = repo / "content" / "en" / "docs"
    for path in sorted(docs.rglob("*.md")):
        relative = path.relative_to(repo).as_posix()
        with path.open() as lines:
            yield from sections_of(
                lines,
                version=version,
                path=relative,
                release_url=release_url,
                source=source,
                license=license,
            )


def sections_from_checkout(repo, source, license):
    """Yield every English docs section for the release this checkout documents."""
    repo = Path(repo)
    release = release_for((repo / "hugo.toml").read_text())
    yield from sections_under(
        repo,
        version=release["version"],
        release_url=release["url"],
        source=source,
        license=license,
    )


def visible_word(match, version):
    shortcode = match.group(0)
    if shortcode == "{{< skew currentVersion >}}":
        return version
    found = re.search(r'text="([^"]*)"', shortcode)
    if found is None:
        return ""
    return found.group(1)


def visible_heading(text):
    headings = {
        "whatsnext": "What's next",
        "objectives": "Objectives",
        "prerequisites": "Before you begin",
        "synopsis": "Synopsis",
        "options": "Options",
        "seealso": "See Also",
        "parentoptions": "Parent Options Inherited",
        "examples": "Examples",
        "cleanup": "Cleaning up",
        "envvars": "Environment variables",
    }
    match = re.fullmatch(r'\{\{% heading "([^"]+)" %\}\}', text)
    if match is None:
        return text
    return headings.get(match.group(1), text)
    
def chunk_page(lines, version=DOCS_VERSION, path="", release_url="", source="", license=""):
    """Yield one section at a time from a docs page."""
    heading = None
    in_fence = False
    held = None
    body = []
    lines = iter(lines)
    first = next(lines, "")
    if first.strip() == "---":
        for line in lines:
            if line.strip() == "---":
                break

    def finished_section():
        if release_url:
            url = page_url(release_url, path)
        else:
            url = ""
        return {
            "heading": heading,
            "text": "\n".join(body).strip(),
            "version": version,
            "path": path,
            "url": url,
            "source": source,
            "license": license,
        }

    def take(line):
        nonlocal heading, body, in_fence, held
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
        elif not in_fence and stripped.startswith("#"):
            finished = None
            if heading is not None:
                finished = finished_section()
            heading = visible_heading(stripped.lstrip("#").strip())
            body = []
            return finished
        elif (
            not in_fence
            and stripped.startswith(("{{<", "{{%"))
            and stripped.endswith((">}}", "%}}"))
        ):
            return None
        elif (
            not in_fence
            and stripped.startswith("<!--")
            and stripped.endswith("-->")
        ):
            return None
        if not in_fence:
            if held is not None:
                stripped = held + stripped
                held = None
            if (
                ("{{<" in stripped or "{{%" in stripped)
                and ">}}" not in stripped
                and "%}}" not in stripped
            ):
                held = stripped
                return None
        stripped = re.sub(
            r"\{\{< .+? >\}\}",
            lambda match: visible_word(match, version),
            stripped,
        )
        if heading is not None and stripped:
            body.append(stripped)
        return None

    if first.strip() != "---":
        finished = take(first)
        if finished is not None:
            yield finished

    for line in lines:
        finished = take(line)
        if finished is not None:
            yield finished

    if heading is not None:
        yield finished_section()