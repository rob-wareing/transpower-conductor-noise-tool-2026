"""Helpers for unit-testing Dash callbacks without a browser.

Dash callbacks are ordinary Python functions, but they're registered as
closures inside each tab's `register_callbacks(dash_app, backend_url)` and
never exposed by name, so they can't be imported and called directly. The
approach here instead drives them the same way a real browser does: POST a
synthetic request shape to the app's own `/_dash-update-component` endpoint
via Flask's test client, and read the callback's return value back out of
the JSON response. This exercises the *actual* registered callback (argument
order, Output/Input/State wiring, prevent_initial_call, etc.) rather than a
hand-extracted copy of its logic.
"""


def _output_key(outputs):
    parts = [f"{component_id}.{prop}" for component_id, prop in outputs]
    return parts[0] if len(parts) == 1 else ".." + "...".join(parts) + ".."


def _candidate_keys(app, exact):
    """All callback_map keys that could plausibly serve `exact` ("id.prop").

    Normally there's exactly one: the plain "id.prop" key itself. But a
    callback registered with Output(..., allow_duplicate=True) gets a key
    with a hashed suffix instead ("id.prop@<hash>"), *specifically* because
    more than one callback is allowed to target the same output - so the
    plain key and one or more hashed keys can legitimately coexist for the
    same output (e.g. a table's "refresh" callback and its "add row"
    callback both writing to the same DataTable's `data` prop). Return every
    key that could be it; the caller disambiguates by matching Inputs.
    """
    return [key for key in app.callback_map if key == exact or key.startswith(f"{exact}@")]


def _resolve_output_key(app, outputs, inputs):
    """Find the callback_map key for `outputs` that's actually wired to the
    given `inputs`, disambiguating between a plain key and any
    allow_duplicate-hashed sibling keys targeting the same output (see
    `_candidate_keys`) by matching each candidate's registered Input list.
    """
    exact = _output_key(outputs)
    if len(outputs) > 1:
        # Multi-output callbacks don't currently collide with allow_duplicate
        # siblings anywhere in this app; only single-output lookups need the
        # extra disambiguation.
        if exact in app.callback_map:
            return exact
        raise KeyError(f"No registered callback found for outputs {outputs}")

    candidates = _candidate_keys(app, exact)
    if not candidates:
        raise KeyError(f"No registered callback found for output {exact}")
    if len(candidates) == 1:
        return candidates[0]

    wanted_inputs = {(component_id, prop) for component_id, prop, _ in inputs}
    matches = [
        key
        for key in candidates
        if {(entry["id"], entry["property"]) for entry in app.callback_map[key]["inputs"]}
        == wanted_inputs
    ]
    if len(matches) == 1:
        return matches[0]
    raise KeyError(
        f"Could not uniquely resolve output {exact} among candidates {candidates} "
        f"for inputs {sorted(wanted_inputs)} - check the Input list passed to dispatch_callback."
    )


def dispatch_callback(app, outputs, inputs, state=None):
    """Invoke a registered callback and return the raw Flask test response.

    `outputs` is a list of (component_id, prop) tuples (order must match the
    callback's own Output(...) order). `inputs`/`state` are lists of
    (component_id, prop, value) tuples, matching the callback's Input/State
    order. A no_update return comes back as HTTP 204 with an empty body.
    """
    state = state or []
    outputs_payload = (
        {"id": outputs[0][0], "property": outputs[0][1]}
        if len(outputs) == 1
        else [{"id": component_id, "property": prop} for component_id, prop in outputs]
    )
    payload = {
        "output": _resolve_output_key(app, outputs, inputs),
        "outputs": outputs_payload,
        "inputs": [
            {"id": component_id, "property": prop, "value": value}
            for component_id, prop, value in inputs
        ],
        "state": [
            {"id": component_id, "property": prop, "value": value}
            for component_id, prop, value in state
        ],
        "changedPropIds": [f"{component_id}.{prop}" for component_id, prop, _ in inputs],
    }
    return app.server.test_client().post("/_dash-update-component", json=payload)


def output_value(response, component_id, prop):
    """Pull one output's value out of a `dispatch_callback` response.

    Only valid when the callback didn't return no_update for that output
    (check `response.status_code != 204` first if that's a possibility).
    """
    return response.get_json()["response"][component_id][prop]
