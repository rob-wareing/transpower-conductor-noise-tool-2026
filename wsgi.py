from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.frontend.app import create_dashboard

backend_app = create_app()
dash_app = create_dashboard(backend_app, backend_url="http://127.0.0.1:5000")
app = dash_app.server


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
