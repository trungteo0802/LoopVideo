# Audio + Video + Intro Batch Progress Design

## Scope

Upgrade only the `Audio + Video + Intro` tab. Keep the `Loop Video` tab and its
current behavior unchanged.

## Goals

- Show continuous human-readable processing activity.
- Show the complete FFmpeg technical log separately.
- Show current-file and whole-batch percentage.
- Show total, completed, failed, and waiting counts.
- Support recursive loading of large audio folder trees.
- Preview the intro matched to every audio before processing.
- Continue processing later audio files after an item-level failure.

## Input loading

`Nạp thư mục audio` scans the selected root recursively for all supported audio
extensions. Deduplicate inputs by resolved absolute path while preserving the
stable sorted order.

Replace the audio `Listbox` with a `Treeview` containing:

- sequence number;
- audio file name;
- channel or relative parent folder;
- duration;
- matched intro;
- status;
- progress percentage.

Load file paths immediately. Probe durations and intro matches in a background
metadata worker so thousands of files do not freeze Tk's event loop. Update the
tree only from the main UI thread through queue events.

Intro matching keeps the existing priority:

1. exact audio parent-folder name;
2. audio filename prefix;
3. default intro;
4. no intro, clearly shown as `Không có intro`.

Refresh preview metadata when the intro folder or default intro changes.

## Progress model

Add four counters above the progress area:

- `Tổng`;
- `Hoàn tất`;
- `Thất bại`;
- `Đang chờ`.

Add two determinate progress bars:

- `File hiện tại`: percentage of the active audio job;
- `Toàn batch`: `(completed + failed + current_fraction) / total`.

The active row shows its current stage and percentage. Stages include probing,
preparing illustration cycle, normalizing intro, looping illustration, joining
visual parts, muxing narration, complete, failed, and stopped.

FFmpeg commands report machine-readable progress using `-progress pipe:2` and
`-nostats`. Parse `out_time_us` or `out_time_ms` against the expected duration.
Clamp values to 0-100 and tolerate missing or non-monotonic timestamps. Commands
without a meaningful target duration still emit stage-level activity.

## Logs

Place a nested notebook below the file table with two tabs.

### Tiến trình

Show concise timestamped events:

- batch start and configuration;
- current audio and channel;
- matched intro;
- current processing stage;
- output path;
- completion, failure, cancellation, and final summary.

### FFmpeg Log

Stream every FFmpeg stderr line while the process runs. Keep the most recent
10,000 lines in the widget to avoid unbounded memory growth during multi-hour
batches. The full session log is also written incrementally as UTF-8 to a safe
temporary or application log file.

Provide `Xóa hiển thị` and `Lưu log...` controls. Saving copies the current
session log to a user-selected file.

## Error handling

Validate global configuration before starting. Treat errors in cycle creation
as batch-level failures because no output can proceed. Treat per-audio probing,
intro, loop, concat, mux, or output errors as item-level failures: mark the row,
increment failed count, record the error, clean temporary files, and continue.

Cancellation terminates the current FFmpeg child process, marks the current row
as stopped, preserves completed outputs, and exits without starting new items.

## Large batches

- Do not impose an application file-count limit.
- Process one output at a time to avoid NVENC, disk, and temporary-file
  contention.
- Avoid probing all files synchronously.
- Batch UI updates to keep the event queue responsive.
- Do not retain full FFmpeg output indefinitely in memory.
- Show recursive relative paths so channels remain distinguishable.

## Testing

- Unit-test recursive discovery and deduplication.
- Unit-test intro preview priority and missing-intro display.
- Unit-test FFmpeg progress parsing and batch-percentage calculations.
- Unit-test log line retention.
- Integration-test a generated audio, intro, and illustration fixture.
- Verify one intentionally invalid audio fails while a later valid audio
  completes.
- Verify cancellation terminates FFmpeg and prevents the next item from
  starting.
- Build the one-file EXE and verify bundled ttkbootstrap and FFmpeg assets.
