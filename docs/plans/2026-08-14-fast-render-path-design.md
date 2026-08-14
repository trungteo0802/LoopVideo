# Fast Render Path Design

## Goal

Avoid re-encoding and duplicating multi-hour illustration videos when the video
stream is already suitable for the final output. Preserve seamless blending for
the original short-loop workflow.

## Strategy selection

Illustration videos at or below 60 seconds use the existing seamless-cycle
builder. The short source is normalized to 1080p30, blended at its boundary,
and encoded once. The resulting small cycle is then looped directly while the
final audio is muxed.

Illustration videos above 60 seconds use a direct-copy fast path. They are
treated as already-produced visual tracks and are not passed through scale,
fps, xfade, or NVENC. FFmpeg reads the source with `-stream_loop -1`, copies the
H.264 video packets, encodes only the final AAC audio, and stops at the combined
audio duration. This also handles a channel audio intro that makes the target a
few seconds longer than the source.

## I/O reduction

For outputs without an optional visual intro, FFmpeg writes the final `_FULL`
file directly. The old pipeline first wrote a full-duration silent loop file
and then read that large temporary file again to mux narration. Removing that
intermediate cuts approximately one full output write and one full output read
per item.

When a visual intro video is configured, the existing part-concatenation path
remains because it must prepend a separate visual stream. Long illustration
tails still use stream copy, while short illustration clips retain their
seamless cycle.

## Correctness and fallback

The audio intro plus narration remains the duration authority. Final output is
limited to that combined duration. Stream-copy failures remain item-level
errors so the batch continues and the FFmpeg log retains the exact diagnostic.
The UI log identifies `Fast copy` or `Seamless short loop` for each item.

## Validation

Tests cover the 60-second strategy boundary and final looped mux command. A
small FFmpeg integration compares output duration and codecs. A real K2 file is
benchmarked over a short target interval to confirm that video is copied rather
than encoded. Existing eleven tests must remain green, followed by a clean EXE
build and startup check.
