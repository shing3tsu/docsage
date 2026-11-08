import re


def visible_word(match):
    found = re.search(r'text="([^"]*)"', match.group(0))
    if found is None:
        return ""
    return found.group(1)
    
def chunk_page(lines):
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

    def take(line):
        nonlocal heading, body, in_fence, held
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
        elif not in_fence and stripped.startswith("#"):
            finished = None
            if heading is not None:
                finished = {"heading": heading, "text": "\n".join(body).strip()}
            heading = stripped.lstrip("#").strip()
            body = []
            return finished
        elif (
            not in_fence
            and stripped.startswith(("{{<", "{{%"))
            and stripped.endswith((">}}", "%}}"))
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
            stripped = re.sub(r"\{\{< .+? >\}\}", visible_word, stripped)
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
        yield {"heading": heading, "text": "\n".join(body).strip()}