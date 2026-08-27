from pathlib import Path

import dash_bootstrap_components as dbc
from dash import dcc, html

# Each sub-tab renders one markdown file from here rather than hardcoded
# Python content - lets the actual wording be edited (by anyone, not just via
# a code change) without touching this file. See "Known gotchas"/repo layout
# notes for why this lives under the frontend package rather than a
# repo-root folder: everything under src/ ships in the web image already, no
# separate Dockerfile COPY line needed.
MARKDOWN_DIR = Path(__file__).resolve().parent.parent / "markdown"

# (sub-tab label, markdown filename) - order here is the order tabs render in.
SUB_TABS = [
    ("General", "general.md"),
    ("Detection logic", "detection_logic.md"),
    ("Charts tab", "charts_tab.md"),
    ("Sites tab", "sites_tab.md"),
    ("Other table tabs", "other_table_tabs.md"),
    ("Locations tab", "locations_tab.md"),
    ("Weather tab", "weather_tab.md"),
]


def _load_markdown(filename):
    path = MARKDOWN_DIR / filename
    if not path.exists():
        return f"_Missing markdown file: `{filename}`_"
    return path.read_text()


def _sub_tab_id(filename):
    return f"help-{filename.removesuffix('.md').replace('_', '-')}"


def content():
    return html.Div(
        [
            html.H2("Help"),
            dbc.Tabs(
                [
                    dbc.Tab(
                        dcc.Markdown(_load_markdown(filename), className="mt-3"),
                        label=label,
                        tab_id=_sub_tab_id(filename),
                    )
                    for label, filename in SUB_TABS
                ]
            ),
        ]
    )
