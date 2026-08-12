# Mint Tabbed Loop Video Suite Design

## Goal

Redesign Loop Video Suite as one comfortable desktop window containing both
existing workflows in a tab strip. Preserve all processing behavior while
replacing the launcher and separate child windows with an integrated interface.

## Visual direction

Use the approved `05 Mint Workspace` direction.

- Light mode: pale mint application background, white working surfaces, dark
  green-black text, emerald primary actions, and orange warning accents.
- Dark mode: deep moss and charcoal-green surfaces, warm off-white text,
  brighter emerald actions, and amber warnings.
- Maintain at least 4.5:1 contrast for normal text.
- Use color together with text or symbols for status and errors.
- Use comfortable spacing, large click targets, visible labels, and clear focus
  states.
- Remember the last selected theme in a user settings file and restore it at
  startup.

The approved reference is `design/mockups/05-mint-workspace.png`.

## Application structure

Create one `LoopVideoSuiteApp` root window. Remove the launcher behavior that
starts separate processes. Place a persistent header and a tab strip above a
shared content region.

Tabs:

1. `Loop Video`
2. `Audio + Video + Intro`

Each tab owns its widgets, selected inputs, task settings, worker state,
progress, and log. Switching tabs must not clear or recreate its state. Both
tabs share FFmpeg discovery, encoding utilities, theme services, common widget
builders, and application shutdown handling.

Only one encoding job may run at a time in the initial version. This prevents
two tabs from competing for NVENC capacity, temporary storage, and disk I/O.
When one tab is active, the other tab remains inspectable but its start action
is disabled. The running tab displays a status marker and progress text in the
tab strip.

## Layout

The header contains the product mark, application name, FFmpeg/GPU status, and
a Light/Dark toggle. The tab strip sits directly below the header.

Each tab uses the same two-column layout:

- Left settings column: approximately 360 logical pixels at normal desktop
  size. It contains grouped labeled inputs, estimates, the primary start action,
  and stop action.
- Right workspace: stretches with the window. It contains input actions,
  drag-and-drop affordance where supported, a scrollable batch list, progress,
  current output information, and collapsible processing log.

At narrower window sizes the settings column remains readable and the file
workspace receives horizontal priority. The minimum supported application size
is 1100 x 720. Controls use a minimum height close to 44 pixels where practical.

## Loop Video tab

Preserve all existing functions:

- `1-1`: each source creates a separate long video.
- `1-nhieu`: all selected sources form one seamless cycle and one output.
- Unlimited file selection from picker or folder.
- User-entered hours and minutes.
- Configurable crossfade.
- Configurable target bitrate and estimated output size.
- NVIDIA NVENC toggle with CPU fallback.
- Output folder selection, cancellation, progress, and detailed log.

The batch list shows file name, source duration, dimensions when available,
size, and processing status. Status values include waiting, processing,
complete, skipped, stopped, and failed.

## Audio + Video + Intro tab

Preserve all existing functions:

- Unlimited narration audio batch selection, including recursive folder load.
- Illustration video folder selection.
- Per-channel intro directory and optional default intro.
- Automatic narration duration probing.
- Intro at the start of the visual track.
- Illustration cycle repeated for the remaining duration.
- Narration muxed as AAC and output named `<audio_stem>_FULL.mp4`.
- Per-channel output subdirectories.
- Configurable crossfade, bitrate, NVENC, cancellation, progress, and log.

The batch list shows channel, audio name, duration, matched intro, output target,
and status. Intro matching remains based on parent folder name first, then audio
name prefix, then default intro.

## Architecture and data flow

Refactor UI concerns away from FFmpeg operations without rewriting verified
processing algorithms.

- `video_loop_tool.py`: retain and improve `FFmpegLoopEngine` as the shared
  processing layer.
- `loop_video_suite.py`: become the integrated application root, theme manager,
  shared task coordinator, and tab host.
- UI tab classes: encapsulate Loop and Audio Full controls and state. They may
  initially live in dedicated modules to keep the root class small.
- Settings service: read and atomically write theme and safe UI preferences in
  `%APPDATA%/LoopVideoSuite/settings.json`.
- Worker communication: use thread-safe queues. All Tk widget changes happen on
  the main thread through scheduled polling.

Start actions validate input, snapshot widget values into immutable task
settings, acquire the shared task coordinator, disable conflicting actions, and
start a daemon worker. Workers emit structured events for status, per-item
updates, progress, logs, completion, cancellation, and errors. The application
root routes events to the owning tab and releases the coordinator at terminal
states.

## Error handling

- Validate missing files, invalid folders, zero duration, bitrate, and fade
  values before starting.
- Detect FFmpeg, ffprobe, and NVENC availability at startup and show explicit
  text status in the header.
- If NVENC is selected but initialization fails, report the cause and offer CPU
  mode rather than silently changing output behavior.
- Continue batch processing after a single item failure when safe; record the
  failed item and error while processing later items.
- Confirm before overwriting an existing output or use a deterministic unique
  suffix based on the final product decision during implementation.
- On window close during a task, ask whether to stop and exit. Terminate the
  active FFmpeg child process and allow temporary-directory cleanup.
- Never manipulate Tk widgets from worker threads.

## Accessibility and interaction

- Every field has a persistent visible label.
- Keyboard tab order follows the visual order.
- Focus rings remain visible in both themes.
- Primary, secondary, destructive, disabled, success, and warning states use
  text and shape differences in addition to color.
- Progress always includes a numeric value and item count.
- Buttons remain disabled while their action is unavailable, with adjacent
  status text explaining why when needed.
- Do not use emoji as interface icons. Use simple vector-like canvas glyphs or
  text labels consistently within Tkinter limitations.

## Testing and verification

Automated checks:

- Compile all changed Python modules.
- Unit-test duration formatting, size estimation, intro matching, settings
  persistence, theme restoration, and task coordinator locking.
- Test FFmpeg command construction for GPU and CPU paths.
- Run an integration fixture with generated short video, intro, and audio.
- Verify the `_FULL.mp4` container duration equals narration duration and
  contains H.264 video plus AAC audio.
- Verify loop outputs respect requested target duration within container/frame
  tolerance.

Manual checks:

- Open both tabs, populate them, switch repeatedly, and confirm state remains.
- Start a job and verify the other tab cannot start a competing job.
- Stop processing and confirm the child process terminates cleanly.
- Restart the app and confirm the last Light/Dark choice is restored.
- Inspect both themes at minimum and normal window sizes for clipping, contrast,
  focus visibility, and readable disabled states.
- Build and launch the bundled one-file EXE with embedded FFmpeg/ffprobe.

## Delivery

Build `LoopVideoSuite.exe` as the primary application. Keep the legacy source
modules and standalone EXEs available during migration, but direct users to the
integrated Suite. Update README usage instructions and push the implementation
to the existing `main` branch after validation.
