from backend.models import ConfigEntry


def test_config_entry_holds_fields():
    entry = ConfigEntry(
        domain="clickshare",
        key="clickshare.button.timeout",
        value="30",
        editable=True,
    )
    assert entry.domain == "clickshare"
    assert entry.key == "clickshare.button.timeout"
    assert entry.value == "30"
    assert entry.editable is True
