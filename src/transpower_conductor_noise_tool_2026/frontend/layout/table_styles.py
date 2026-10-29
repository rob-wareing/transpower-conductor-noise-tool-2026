EDITABLE_CELL_HIGHLIGHT = [
    {"if": {"column_editable": True}, "backgroundColor": "rgb(179, 255, 179)", "color": "black"}
]

# Rows that failed to save carry a "save_error" string (see callbacks/outages.py).
# Listed after EDITABLE_CELL_HIGHLIGHT so it wins on editable cells too.
SAVE_ERROR_HIGHLIGHT = [
    {
        "if": {"filter_query": "{save_error} is str"},
        "backgroundColor": "rgb(255, 204, 204)",
        "color": "black",
    }
]

BOLD_LEFT_ALIGN_HEADER = {"textAlign": "left", "fontWeight": "bold"}
