import re

import flask

from transpower_conductor_noise_tool_2026.frontend.app import create_dashboard
from transpower_conductor_noise_tool_2026.frontend.layout import help as help_layout


def _rendered_text(component):
    return repr(component)


def test_content_includes_every_sub_tab_label():
    text = _rendered_text(help_layout.content())

    for label, _filename in help_layout.SUB_TABS:
        assert label in text


def test_content_renders_each_sub_tabs_markdown_file_content():
    text = _rendered_text(help_layout.content())

    for _label, filename in help_layout.SUB_TABS:
        path = help_layout.MARKDOWN_DIR / filename
        assert path.exists(), f"missing markdown file: {filename}"
        # A couple of words from each file's own content, not the whole
        # (multi-paragraph) file, to keep this robust to future wording edits.
        first_line = path.read_text().splitlines()[0]
        assert first_line in text


def test_detection_logic_markdown_includes_the_comparison_table():
    content = (help_layout.MARKDOWN_DIR / "detection_logic.md").read_text()

    for column in ["Criteria", "Original", "Updated 2026"]:
        assert column in content
    assert "Line status" in content


def test_load_markdown_returns_placeholder_message_for_missing_file():
    text = help_layout._load_markdown("does-not-exist.md")

    assert "does-not-exist.md" in text


def test_sub_tab_id_is_unique_per_file():
    ids = [help_layout._sub_tab_id(filename) for _label, filename in help_layout.SUB_TABS]

    assert len(ids) == len(set(ids))


def test_markdown_image_links_point_at_the_help_media_route():
    text = _rendered_text(help_layout.content())

    assert "](./gifs/" not in text
    assert f"]({help_layout.HELP_MEDIA_URL}" in text


def test_every_referenced_help_image_exists():
    for _label, filename in help_layout.SUB_TABS:
        markdown = help_layout._load_markdown(filename)
        for name in re.findall(re.escape(help_layout.HELP_MEDIA_URL) + r"([^\s)]+)", markdown):
            assert (help_layout.HELP_MEDIA_DIR / name).exists(), f"{filename} -> {name}"


def test_help_media_route_serves_the_image_file():
    dash_app = create_dashboard(flask.Flask(__name__))
    name = next(help_layout.HELP_MEDIA_DIR.glob("*.gif")).name

    response = dash_app.server.test_client().get(f"{help_layout.HELP_MEDIA_URL}{name}")

    assert response.status_code == 200
    assert response.mimetype == "image/gif"


def test_help_media_route_404s_for_unknown_file():
    dash_app = create_dashboard(flask.Flask(__name__))

    response = dash_app.server.test_client().get(f"{help_layout.HELP_MEDIA_URL}nope.gif")

    assert response.status_code == 404
