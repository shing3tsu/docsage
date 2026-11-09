import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from clean import (
    chunk_page,
    docs_releases,
    docs_version,
    release_for,
    page_url,
    point_id,
    sections_of,
    sections_under,
)

PAGE = Path(__file__).resolve().parent / "testdata" / "page.md"


def test_chunk_page_drops_front_matter_and_splits_on_headings():
    with PAGE.open() as lines:
        sections = list(chunk_page(lines, path="testdata/page.md"))

    assert sections == [
        {
            "heading": "Pods",
            "text": "A pod is a group of containers.",
            "version": "1.37",
            "path": "testdata/page.md",
            "url": "",
            "source": "",
            "license": "",
        },
        {
            "heading": "What is a pod?",
            "text": "The spec is the desired state.",
            "version": "1.37",
            "path": "testdata/page.md",
            "url": "",
            "source": "",
            "license": "",
        },
    ]


def test_chunk_page_stores_the_public_link_for_a_release():
    page = """\
# Pods

A pod is a group of containers.
"""
    sections = list(
        chunk_page(
            page.splitlines(True),
            path="content/en/docs/concepts/workloads/pods/_index.md",
            release_url="https://kubernetes.io",
            source="kubernetes",
            license="CC BY 4.0",
        )
    )

    assert sections == [
        {
            "heading": "Pods",
            "text": "A pod is a group of containers.",
            "version": "1.37",
            "path": "content/en/docs/concepts/workloads/pods/_index.md",
            "url": "https://kubernetes.io/docs/concepts/workloads/pods/",
            "source": "kubernetes",
            "license": "CC BY 4.0",
        }
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
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
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
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
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
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
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
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
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
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
        }
    ]

def test_chunk_page_drops_an_html_comment():
    page = """\
# Pods

<!--intentionally repeats some text from earlier in the page, with more detail -->
A pod groups containers.
"""
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "Pods",
            "text": "A pod groups containers.",
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
        }
    ]

def test_chunk_page_uses_the_visible_words_of_a_heading_shortcode():
    page = """\
## {{% heading "whatsnext" %}}

Learn about the lifecycle of a Pod.
"""
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "What's next",
            "text": "Learn about the lifecycle of a Pod.",
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
        }
    ]

def test_chunk_page_uses_the_visible_words_of_an_objectives_heading():
    page = """\
## {{% heading "objectives" %}}

Learn what a Pod is.
"""
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "Objectives",
            "text": "Learn what a Pod is.",
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
        }
    ]


def test_chunk_page_uses_the_visible_words_of_a_prerequisites_heading():
    page = """\
## {{% heading "prerequisites" %}}

Install a container runtime.
"""
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "Before you begin",
            "text": "Install a container runtime.",
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
        }
    ]

def test_chunk_page_uses_the_visible_words_of_a_synopsis_heading():
    page = """\
## {{% heading "synopsis" %}}

Print the pods.
"""
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "Synopsis",
            "text": "Print the pods.",
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
        }
    ]

def test_chunk_page_replaces_the_current_version_shortcode():
    page = """\
# Pods

The latest release is {{< skew currentVersion >}}.
"""
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "Pods",
            "text": "The latest release is 1.37.",
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
        }
    ]

def test_chunk_page_replaces_a_version_shortcode_inside_a_code_fence():
    page = """\
# Pods

```shell
# replace x with the latest patch
sudo apt-get install kubeadm='{{< skew currentVersion >}}.x-*'
```
"""
    sections = list(chunk_page(page.splitlines(True)))

    assert sections == [
        {
            "heading": "Pods",
            "text": "```shell\n# replace x with the latest patch\nsudo apt-get install kubeadm='1.37.x-*'\n```",
            "version": "1.37",
            "path": "",
            "url": "",
            "source": "",
            "license": "",
        }
    ]


def test_docs_version_reads_the_release_from_hugo_toml():
    hugo_toml = """\
latest = "v1.37"
version = "v1.37"
version = "v1.36"
"""
    assert docs_version(hugo_toml) == "1.37"


def test_docs_releases_lists_each_published_version():
    hugo_toml = """\
latest = "v1.37"
version = "v1.37"
docsbranch = "main"

[[params.versions]]
version = "v1.37"
docsbranch = "main"
url = "https://kubernetes.io"

[[params.versions]]
version = "v1.36"
docsbranch = "release-1.36"
url = "https://v1-36.docs.kubernetes.io"
"""
    assert docs_releases(hugo_toml) == [
        {
            "version": "1.37",
            "branch": "main",
            "url": "https://kubernetes.io",
            "latest": True,
        },
        {
            "version": "1.36",
            "branch": "release-1.36",
            "url": "https://v1-36.docs.kubernetes.io",
            "latest": False,
        },
    ]


def test_release_for_returns_the_checkout_version():
    hugo_toml = """\
latest = "v1.37"
version = "v1.37"
docsbranch = "main"

[[params.versions]]
version = "v1.37"
docsbranch = "main"
url = "https://kubernetes.io"

[[params.versions]]
version = "v1.36"
docsbranch = "release-1.36"
url = "https://v1-36.docs.kubernetes.io"
"""
    assert release_for(hugo_toml) == {
        "version": "1.37",
        "branch": "main",
        "url": "https://kubernetes.io",
        "latest": True,
    }
    older = hugo_toml.replace('version = "v1.37"\ndocsbranch', 'version = "v1.36"\ndocsbranch', 1)
    assert release_for(older) == {
        "version": "1.36",
        "branch": "release-1.36",
        "url": "https://v1-36.docs.kubernetes.io",
        "latest": False,
    }


def test_page_url_builds_the_public_link_for_a_docs_file():
    assert (
        page_url(
            "https://kubernetes.io",
            "content/en/docs/concepts/workloads/pods/_index.md",
        )
        == "https://kubernetes.io/docs/concepts/workloads/pods/"
    )
    assert (
        page_url(
            "https://v1-36.docs.kubernetes.io/",
            "content/en/docs/concepts/workloads/pods/pod-lifecycle.md",
        )
        == "https://v1-36.docs.kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/"
    )


def test_point_id_is_stable_for_one_section_and_changes_with_position():
    kwargs = {
        "source": "kubernetes",
        "version": "1.37",
        "path": "content/en/docs/concepts/workloads/pods/_index.md",
        "heading": "Pods",
    }
    first = point_id(**kwargs, position=0)
    again = point_id(**kwargs, position=0)
    moved = point_id(**kwargs, position=1)

    assert first == again
    assert first != moved
    assert len(first) == 64


def test_sections_of_assigns_a_stable_id_to_each_section():
    with PAGE.open() as lines:
        sections = list(
            sections_of(
                lines,
                version="1.37",
                path="testdata/page.md",
                release_url="",
                source="kubernetes",
                license="CC BY 4.0",
            )
        )

    assert [section["heading"] for section in sections] == [
        "Pods",
        "What is a pod?",
    ]
    assert sections[0]["id"] != sections[1]["id"]
    assert sections[1]["id"] == point_id(
        "kubernetes",
        "1.37",
        "testdata/page.md",
        "What is a pod?",
        1,
    )

def test_sections_under_reads_every_docs_page(tmp_path):
    pods = tmp_path / "content" / "en" / "docs" / "concepts" / "workloads" / "pods"
    pods.mkdir(parents=True)
    (pods / "_index.md").write_text("# Pods\n\nA pod is a group of containers.\n")
    (pods / "pod-lifecycle.md").write_text("# Pod lifecycle\n\nA pod starts and stops.\n")
    (tmp_path / "README.md").write_text("# Ignore me\n")

    sections = list(
        sections_under(
            tmp_path,
            version="1.37",
            release_url="https://kubernetes.io",
            source="kubernetes",
            license="CC BY 4.0",
        )
    )

    assert [section["path"] for section in sections] == [
        "content/en/docs/concepts/workloads/pods/_index.md",
        "content/en/docs/concepts/workloads/pods/pod-lifecycle.md",
    ]
    assert sections[0]["id"] != sections[1]["id"]
    assert sections[0]["url"] == "https://kubernetes.io/docs/concepts/workloads/pods/"
