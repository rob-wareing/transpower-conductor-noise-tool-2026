import dash
import dash_bootstrap_components as dbc
import flask
from dash import Input, Output, dcc, html

from .callbacks.charts import register_callbacks as register_chart_callbacks
from .callbacks.historical import register_callbacks as register_historical_callbacks
from .callbacks.outages import register_callbacks as register_outage_callbacks
from .callbacks.reconductoring import register_callbacks as register_reconductoring_callbacks
from .callbacks.sites import register_callbacks as register_site_callbacks
from .client import BackendClient
from .layout import charts as charts_layout
from .layout import historical as historical_layout
from .layout import outages as outages_layout
from .layout import reconductoring as reconductoring_layout
from .layout import sites as sites_layout

LOGIN_FORM = """
<!doctype html>
<title>Log in</title>
<h1>Conductor Noise Tool 2026</h1>
{error}
<form method="post" action="/login">
  <label>Email <input type="email" name="email" required></label><br>
  <label>Password <input type="password" name="password" required></label><br>
  <button type="submit">Log in</button>
</form>
"""


def _relay_cookies(backend_response, flask_response):
    for cookie in backend_response.cookies:
        flask_response.set_cookie(cookie.name, cookie.value, httponly=True, samesite="Lax")


def _register_auth_routes(server, client: BackendClient | None):
    @server.get("/login")
    def login_form():
        return LOGIN_FORM.format(error="")

    @server.post("/login")
    def login_submit():
        if client is None:
            return LOGIN_FORM.format(error="<p>No backend configured.</p>"), 503

        backend_response = client.login(
            flask.request.form.get("email", ""),
            flask.request.form.get("password", ""),
        )
        if backend_response.status_code != 200:
            return LOGIN_FORM.format(error="<p>Invalid email or password.</p>"), 401

        flask_response = flask.make_response(flask.redirect("/app/"))
        _relay_cookies(backend_response, flask_response)
        return flask_response

    @server.get("/logout")
    def logout():
        if client is not None:
            client.logout(cookies=flask.request.cookies)

        flask_response = flask.make_response(flask.redirect("/login"))
        flask_response.delete_cookie("session")
        return flask_response


def create_dashboard(server=None, backend_url=None):
    client = BackendClient(backend_url) if backend_url else None

    if server is not None:
        _register_auth_routes(server, client)

    dash_app = dash.Dash(
        title="Conductor Noise Tool 2026",
        server=server,
        routes_pathname_prefix="/app/",
        external_stylesheets=[dbc.themes.BOOTSTRAP],
    )
    dash_app.config.suppress_callback_exceptions = True
    dash_app.layout = html.Div(
        [
            dcc.Location(id="url", refresh=True),
            html.Div(id="page-content"),
        ]
    )

    @dash_app.callback(Output("page-content", "children"), Input("url", "pathname"))
    def render_page(_pathname):
        current_user = client.get_current_user(cookies=flask.request.cookies) if client else None
        if current_user is None:
            return dcc.Location(pathname="/login", id="redirect-to-login")

        return html.Div(
            [
                html.H1("Conductor Noise Tool 2026"),
                html.P(f"Signed in as {current_user.name}."),
                html.A("Log out", href="/logout"),
                dbc.Tabs(
                    [
                        dbc.Tab(charts_layout.content(), label="Charts", tab_id="charts"),
                        dbc.Tab(
                            sites_layout.content(write_access=current_user.write_access),
                            label="Sites",
                            tab_id="sites",
                        ),
                        dbc.Tab(
                            outages_layout.content(write_access=current_user.write_access),
                            label="Outages",
                            tab_id="outages",
                        ),
                        dbc.Tab(
                            reconductoring_layout.content(write_access=current_user.write_access),
                            label="Reconductoring",
                            tab_id="reconductoring",
                        ),
                        dbc.Tab(
                            historical_layout.content(write_access=current_user.write_access),
                            label="Historical",
                            tab_id="historical",
                        ),
                    ],
                    active_tab="charts",
                ),
            ]
        )

    register_site_callbacks(dash_app, backend_url)
    register_chart_callbacks(dash_app, backend_url)
    register_outage_callbacks(dash_app, backend_url)
    register_reconductoring_callbacks(dash_app, backend_url)
    register_historical_callbacks(dash_app, backend_url)
    return dash_app
