# Channel Audio Intro Design

## Goal

An audio file named `<channel>-Intro` is a reusable narration intro, not a
standalone batch item. It is prepended to every narration belonging to that
channel. The matched illustration video is looped to the combined duration of
the channel intro plus the narration.

Example:

`K2-Intro.wav + K2-V10.wav + K2-V10.mp4 -> K2-V10_FULL.mp4`

## Discovery and matching

Loading an audio root scans both audio and video recursively. If the separate
illustration directory is empty, it automatically uses the selected audio root,
so sibling `.wav` and `.mp4` files can match without another folder selection.

Audio stems ending in `-Intro` are removed from the narration list and indexed
by the prefix before `-Intro`. A narration finds its channel intro by walking
its ancestor folders first, then by the longest matching filename prefix. Thus
`K2-Intro.wav` applies to narrations inside `K2/K2-V10`, `K2/K2-V11`, and other
descendants. Audio and video stem matching remains case-insensitive.

## Rendering

FFmpeg concatenates the channel intro and narration into a temporary AAC audio
stream with a normalized sample rate and stereo channel layout. The combined
duration is the sum of both source durations. The matched illustration video is
made seamless and repeated to that combined duration. Existing optional video
intro behavior remains available and operates on the visual track only.

The final mux uses the combined audio and combined duration, producing
`<narration-stem>_FULL.mp4`. Temporary audio and video intermediates are removed
with the existing temporary directory.

## UI and errors

The table adds a dedicated `Audio intro` column while preserving the visual
intro column. `*-Intro` audio files never appear as batch narration rows. Logs
show the audio intro, narration, matched illustration, output path, and combined
duration.

If an intro cannot be decoded or concatenated, only that narration fails and
the batch continues. Narrations without a channel audio intro remain valid and
render exactly as before.

## Validation

Tests cover audio-intro classification, ancestor-channel matching, automatic
same-root video discovery behavior, and FFmpeg audio concatenation. Existing
matching, progress, recursive discovery, and UI tests must remain green. The
PyInstaller executable must build and remain running after startup.
