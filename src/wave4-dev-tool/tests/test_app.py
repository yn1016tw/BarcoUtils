from app import Api


def test_api_window_reference_is_private():
    # pywebview's inject_pywebview() walks every public, non-callable
    # attribute of js_api to auto-discover exposed methods. A public
    # `window` attribute pulls in the WinForms native control graph and
    # recurses infinitely through self-referential .NET properties,
    # freezing the app (see app.py's comment on `api._window = window`).
    api = Api()
    assert not hasattr(api, "window")
    assert hasattr(api, "_window")
