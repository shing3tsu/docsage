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
