from pathlib import Path

from loop_video_suite import AudioTab, SettingsStore, batch_percent, discover_audio_files, mint_theme, DARK, LIGHT
from video_loop_tool import FFmpegLoopEngine


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


def test_recursive_audio_discovery_is_sorted_and_filtered(tmp_path: Path) -> None:
    nested = tmp_path / "channel" / "season"
    nested.mkdir(parents=True)
    (nested / "b.mp3").touch()
    (tmp_path / "a.wav").touch()
    (nested / "ignore.txt").touch()

    assert [path.name for path in discover_audio_files(tmp_path)] == ["a.wav", "b.mp3"]


def test_batch_percentage_includes_current_item_fraction() -> None:
    assert batch_percent(2, 1, 50, 5) == 70
    assert batch_percent(0, 0, 50, 0) == 0


def test_ffmpeg_progress_line_parser() -> None:
    assert FFmpegLoopEngine.parse_progress_line("out_time_us=5000000", 10) == 50
    assert FFmpegLoopEngine.parse_progress_line("frame=20", 10) is None
