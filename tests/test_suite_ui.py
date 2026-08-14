from pathlib import Path

from loop_video_suite import AudioTab, SettingsStore, batch_percent, classify_audio_files, classify_video_files, discover_audio_files, find_channel_audio_intro, match_audio_videos, mint_theme, preview_log_lines, DARK, LIGHT
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


def test_preview_log_contains_source_and_destination_paths() -> None:
    videos = [Path("D:/media/scene-1.mp4"), Path("D:/media/scene-2.mp4")]
    audio = Path("D:/audio/channel-a/story.mp3")
    output = Path("D:/output/channel-a/story_FULL.mp4")

    preview = "\n".join(preview_log_lines(videos, audio, output))

    assert "2 files" in preview
    assert str(videos[0]) in preview
    assert str(videos[1]) in preview
    assert str(audio) in preview
    assert output.name in preview
    assert str(output) in preview


def test_video_classification_and_name_matching() -> None:
    paths = [
        Path("D:/video/K2-V10.mp4"),
        Path("D:/video/K2-Intro.mp4"),
        Path("D:/video/unused.mov"),
    ]
    illustrations, intros, duplicates = classify_video_files(paths)
    audio = Path("D:/audio/K2/K2-v10.wav")

    matches, missing_audio = match_audio_videos([audio], illustrations)

    assert matches[audio] == paths[0]
    assert intros["k2"] == paths[1]
    assert paths[1] not in missing_audio
    assert missing_audio == [paths[2]]
    assert duplicates == []


def test_duplicate_video_stem_uses_first_sorted_path() -> None:
    first = Path("D:/a/story.mp4")
    duplicate = Path("D:/b/STORY.mov")

    illustrations, _intros, duplicates = classify_video_files([duplicate, first])

    assert illustrations["story"] == first
    assert duplicates == [("story", duplicate)]


def test_audio_intro_is_excluded_and_matches_ancestor_channel() -> None:
    channel_intro = Path("D:/TruyenTL/K2/K2-Intro.wav")
    narration = Path("D:/TruyenTL/K2/K2-V10/K2-V10.wav")

    narrations, intros = classify_audio_files([narration, channel_intro])

    assert narrations == [narration]
    assert intros == {"k2": channel_intro}
    assert find_channel_audio_intro(narration, intros) == channel_intro


def test_recursive_discovery_excludes_audio_intro(tmp_path: Path) -> None:
    (tmp_path / "K2-Intro.wav").touch()
    story = tmp_path / "K2-V10" / "K2-V10.wav"
    story.parent.mkdir()
    story.touch()

    assert discover_audio_files(tmp_path) == [story]
