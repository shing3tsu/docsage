import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from clean import chunk_page

PAGE = Path(__file__).resolve().parent / "testdata" / "page.md"


def test_chunk_page_drops_front_matter_and_splits_on_headings():
    with PAGE.open() as lines:
        sections = list(chunk_page(lines))

    assert sections == [
        {"heading": "Pods", "text": "A pod is a group of containers."},
        {"heading": "What is a pod?", "text": "The spec is the desired state."},
    ]

def test_chunk_page_drops_shortcode_markers_and_keeps_the_note_text(): 
    page = """\
    # Pods

    {{< note >}}
    Remember this.
    {{< /note >}}

    A pod groups containers.
    """
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "Pods",
            "text": "Remember this.\nA pod groups containers.",
        }
    ]

def test_chunk_page_keeps_hash_comments_inside_a_code_fence():
    page = """\
# Pods

```yaml
apiVersion: v1
# This is the pod template
kind: Pod
```

A pod groups containers.
"""
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "Pods",
            "text": "```yaml\napiVersion: v1\n# This is the pod template\nkind: Pod\n```\nA pod groups containers.",
        }
    ]


def test_chunk_page_replaces_an_inline_shortcode_with_its_visible_text():
    page = """\
# Pods

A pod isolates a {{< glossary_tooltip text="container" term_id="container" >}}.
"""
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "Pods",
            "text": "A pod isolates a container.",
        }
    ]

def test_chunk_page_replaces_a_shortcode_split_across_lines():
    page = """\
# Pods

Create them using a {{< glossary_tooltip text="Deployment"
term_id="deployment" >}} or a Job.
"""
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "Pods",
            "text": "Create them using a Deployment or a Job.",
        }
    ]


def test_chunk_page_replaces_a_shortcode_split_across_lines():
    page = """\
# Pods

Create them using a {{< glossary_tooltip text="Deployment"
term_id="deployment" >}} or a Job.
"""
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "Pods",
            "text": "Create them using a Deployment or a Job.",
        }
    ]