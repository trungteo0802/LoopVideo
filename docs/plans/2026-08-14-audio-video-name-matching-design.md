# Audio/Video Name Matching Design

## Goal

The `Audio + Video + Intro` tab must show the exact illustration video paired
with every audio file before rendering. Pairing uses the case-insensitive file
stem, so `K2-V10.wav` matches `K2-V10.mp4` regardless of extension.

## Discovery and classification

Audio and illustration folders are scanned recursively. Video files whose stem
ends in `-Intro` are classified as channel intros, excluded from illustration
matching, and keyed by the text before `-Intro`. For example, `K2-Intro.mp4`
becomes the intro for audio files whose parent channel folder is `K2`.

All other videos are illustration candidates. Duplicate stems use the first
path in deterministic case-insensitive sort order and produce a readable log
warning.

## Table behavior

The batch table adds an `Illustration video` column. It displays the matched
video filename for a valid pair. An audio without a same-stem video is marked
`Missing Video`. A video without a same-stem audio is represented by a review
row marked `Missing Audio`; that row is informational and is not rendered.
Intro files never appear as illustration or missing-audio rows.

Refreshing the video folder or adding audio rebuilds the pairing view without
losing the selected audio list. Duration and matched intro metadata continue to
load asynchronously.

## Processing and logs

Each valid audio uses only its same-stem illustration video. FFmpeg creates a
seamless cycle from that video, repeats it to the narration duration, prepends
the matched channel/default intro, and writes `<audio-stem>_FULL.mp4`.

Missing-video audio items are recorded as failed/skipped and the batch
continues. Missing-audio video rows are never submitted to FFmpeg. Before each
valid render, the readable log prints the exact audio path, illustration path,
intro path when present, output filename, and output path.

## Validation

Unit tests cover case-insensitive same-stem matching, intro classification,
missing audio/video detection, and preview log paths. Existing progress parser,
batch percentage, recursive discovery, and theme tests must remain green. The
final executable is rebuilt with the existing PyInstaller specification and
must remain running after startup.
