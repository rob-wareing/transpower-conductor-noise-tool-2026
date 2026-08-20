from transpower_conductor_noise_tool_2026.frontend.layout import help as help_layout


def _rendered_text(component):
    return repr(component)


def test_content_includes_all_four_subheadings():
    text = _rendered_text(help_layout.content())

    for subheading in ["Detection Logic", "Historical Data", "Wind Roses", "Site Location"]:
        assert subheading in text


def test_content_describes_each_feature():
    text = _rendered_text(help_layout.content())

    assert "Updated 2026" in text
    assert "16 direction sectors" in text
    assert "average monthly rainfall" in text


def test_detection_logic_table_has_the_expected_columns_and_rows():
    text = _rendered_text(help_layout.content())

    for column in ["Criteria", "Original", "Updated 2026"]:
        assert column in text

    for criteria, _pre_2026, _updated in help_layout.DETECTION_LOGIC_CRITERIA:
        assert criteria in text


def test_detection_logic_table_marks_line_status_as_live_only_in_updated():
    criteria_by_name = {
        criteria: (pre_2026, updated)
        for criteria, pre_2026, updated in help_layout.DETECTION_LOGIC_CRITERIA
    }

    pre_2026, updated = criteria_by_name["Line status"]

    assert updated == "Live"
    assert pre_2026 != "Live"
