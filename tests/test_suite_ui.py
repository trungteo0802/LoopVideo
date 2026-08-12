from pathlib import Path

from loop_video_suite import AudioTab, SettingsStore, mint_theme, DARK, LIGHT


def test_theme_settings_round_trip(tmp_path: Path) -> None:
    store = SettingsStore()
    store.path = tmp_path / "settings.json"

    assert store.load_theme() == "light"
    store.save_theme("dark")
    assert store.load_theme() == "dark"


def test_mint_theme_definitions() -> None:
    light = mint_theme("test-mint-light", LIGHT, "light")
    dark = mint_theme("test-mint-dark", DARK, "dark")

    assert light.colors.primary == LIGHT["accent"]
    assert light.colors.inputbg == LIGHT["field"]
    assert dark.colors.primary == DARK["accent"]
    assert dark.colors.inputfg == DARK["text"]


def test_intro_matching_priority() -> None:
    channel_intro = Path("channel-a.mp4")
    prefix_intro = Path("prefix.mp4")
    default_intro = Path("default.mp4")
    intros = {"channel-a": channel_intro, "story": prefix_intro}

    assert AudioTab.find_intro(Path("root/channel-a/item.mp3"), intros, default_intro) == channel_intro
    assert AudioTab.find_intro(Path("root/other/story-01.mp3"), intros, default_intro) == prefix_intro
    assert AudioTab.find_intro(Path("root/other/item.mp3"), intros, default_intro) == default_intro
