import re


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
    
def chunk_page(lines, version=DOCS_VERSION, path="", release_url=""):
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