from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def find_ffmpeg_tools() -> tuple[str | None, str | None]:
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    bundled_ffmpeg = bundle_dir / "ffmpeg.exe"
    bundled_ffprobe = bundle_dir / "ffprobe.exe"
    if bundled_ffmpeg.is_file() and bundled_ffprobe.is_file():
        return str(bundled_ffmpeg), str(bundled_ffprobe)

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe

    # WinGet installs can be available before the current process receives the
    # refreshed PATH, so discover their bin directory directly as a fallback.
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        candidates = sorted(
            packages.glob("Gyan.FFmpeg*_8wekyb3d8bbwe/ffmpeg-*/bin"),
            reverse=True,
        )
        for folder in candidates:
            ffmpeg_path = folder / "ffmpeg.exe"
            ffprobe_path = folder / "ffprobe.exe"
            if ffmpeg_path.is_file() and ffprobe_path.is_file():
                return str(ffmpeg_path), str(ffprobe_path)
    return ffmpeg, ffprobe


def format_seconds(value: float) -> str:
    hours, remainder = divmod(int(value), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class FFmpegLoopEngine:
    def __init__(
        self, ffmpeg: str, ffprobe: str, log, stop_event: threading.Event,
        use_gpu: bool = True, bitrate_mbps: float = 10.0,
        raw_log=None, progress=None,
    ) -> None:
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.log = log
        self.stop_event = stop_event
        self.use_gpu = use_gpu
        self.bitrate_mbps = bitrate_mbps
        self.raw_log = raw_log or log
        self.progress_callback = progress
        self.process: subprocess.Popen[str] | None = None

    def duration(self, path: Path) -> float:
        command = [
            self.ffprobe, "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        value = float(json.loads(result.stdout)["format"]["duration"])
        if value <= 0:
            raise ValueError(f"Không đọc được thời lượng: {path.name}")
        return value

    def set_progress_callback(self, callback) -> None:
        self.progress_callback = callback

    @staticmethod
    def parse_progress_line(line: str, expected_duration: float | None) -> float | None:
        if not expected_duration or expected_duration <= 0 or "=" not in line:
            return None
        key, value = line.strip().split("=", 1)
        if key not in {"out_time_us", "out_time_ms"}:
            return None
        try:
            seconds = int(value) / 1_000_000
        except ValueError:
            return None
        return max(0.0, min(100.0, seconds / expected_duration * 100.0))

    def _run(self, command: list[str], expected_duration: float | None = None) -> None:
        self.log(" ".join(f'\"{part}\"' if " " in part else part for part in command))
        command = command[:-1] + ["-progress", "pipe:2", "-nostats", command[-1]]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", creationflags=creationflags,
        )
        assert self.process.stderr is not None
        tail: list[str] = []
        for line in self.process.stderr:
            if self.stop_event.is_set():
                self.process.terminate()
                self.process.wait(timeout=5)
                raise InterruptedError("Đã dừng theo yêu cầu.")
            if line.strip():
                clean = line.strip()
                self.raw_log(clean)
                progress = self.parse_progress_line(clean, expected_duration)
                if progress is not None and self.progress_callback:
                    self.progress_callback(progress)
                tail.append(clean)
                tail = tail[-12:]
        code = self.process.wait()
        self.process = None
        if code != 0:
            raise RuntimeError("FFmpeg thất bại:\n" + "\n".join(tail))
        if expected_duration and self.progress_callback:
            self.progress_callback(100.0)

    def _video_options(self) -> list[str]:
        bitrate = max(1, round(self.bitrate_mbps * 1000))
        rate_options = [
            "-b:v", f"{bitrate}k", "-maxrate", f"{bitrate}k",
            "-bufsize", f"{bitrate * 2}k",
        ]
        if self.use_gpu:
            return [
                "-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq",
                "-rc", "vbr", *rate_options, "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", "-an",
            ]
        return [
            "-c:v", "libx264", "-preset", "medium", *rate_options,
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
        ]

    def make_single_cycle(self, source: Path, destination: Path, fade: float) -> float:
        duration = self.duration(source)
        fade = min(fade, duration / 3)
        if fade < 0.05:
            raise ValueError(f"Video quá ngắn để hòa trộn: {source.name}")
        middle_end = duration - fade
        graph = (
            "[0:v]fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,split=3[a][b][c];"
            f"[a]trim=start={fade}:end={middle_end},setpts=PTS-STARTPTS[mid];"
            f"[b]trim=start={middle_end}:end={duration},setpts=PTS-STARTPTS[tail];"
            f"[c]trim=start=0:end={fade},setpts=PTS-STARTPTS[head];"
            f"[tail][head]xfade=transition=fade:duration={fade}:offset=0[blend];"
            "[mid][blend]concat=n=2:v=1:a=0,format=yuv420p[outv]"
        )
        command = [self.ffmpeg, "-y", "-i", str(source), "-filter_complex", graph, "-map", "[outv]"]
        self._run(command + self._video_options() + [str(destination)], duration - fade)
        return duration - fade

    def make_multi_cycle(self, sources: list[Path], destination: Path, fade: float) -> float:
        durations = [self.duration(path) for path in sources]
        fade = min(fade, min(durations) / 3)
        if fade < 0.05:
            raise ValueError("Có video quá ngắn để hòa trộn.")

        # Duplicate the first clip at the end, then cut at the same point in that
        # duplicate. The cycle therefore ends exactly where its next repeat starts.
        inputs = sources + [sources[0]]
        filters: list[str] = []
        for index in range(len(inputs)):
            filters.append(
                f"[{index}:v]fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,"
                f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS[v{index}]"
            )
        current = "v0"
        elapsed = durations[0]
        for index in range(1, len(inputs)):
            offset = elapsed - fade
            output = f"x{index}"
            filters.append(
                f"[{current}][v{index}]xfade=transition=fade:duration={fade}:offset={offset}[{output}]"
            )
            current = output
            elapsed += (durations[index] if index < len(durations) else durations[0]) - fade
        cycle_duration = sum(durations) - len(sources) * fade
        filters.append(f"[{current}]trim=start={fade}:duration={cycle_duration},setpts=PTS-STARTPTS[outv]")
        command = [self.ffmpeg, "-y"]
        for path in inputs:
            command += ["-i", str(path)]
        command += ["-filter_complex", ";".join(filters), "-map", "[outv]"]
        self._run(command + self._video_options() + [str(destination)], cycle_duration)
        return cycle_duration

    def repeat_cycle(self, cycle: Path, output: Path, target_seconds: int) -> None:
        command = [
            self.ffmpeg, "-y", "-stream_loop", "-1", "-i", str(cycle),
            "-t", str(target_seconds), "-c", "copy", "-an", "-movflags", "+faststart", str(output),
        ]
        self._run(command, float(target_seconds))

    def normalize_intro(self, source: Path, destination: Path, max_duration: float) -> float:
        duration = min(self.duration(source), max_duration)
        graph = (
            "[0:v]fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[outv]"
        )
        command = [
            self.ffmpeg, "-y", "-i", str(source), "-t", f"{duration:.3f}",
            "-filter_complex", graph, "-map", "[outv]",
        ]
        self._run(command + self._video_options() + [str(destination)], duration)
        return duration

    def concat_video_parts(self, parts: list[Path], destination: Path) -> None:
        list_file = destination.with_suffix(".concat.txt")
        lines = []
        for path in parts:
            escaped = str(path.resolve()).replace("'", "'\\''")
            lines.append(f"file '{escaped}'")
        list_file.write_text("\n".join(lines), encoding="utf-8")
        try:
            command = [
                self.ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
                "-c", "copy", "-an", "-movflags", "+faststart", str(destination),
            ]
            self._run(command)
        finally:
            list_file.unlink(missing_ok=True)

    def concat_audio_parts(self, parts: list[Path], destination: Path, expected_duration: float) -> None:
        if len(parts) < 2:
            raise ValueError("Cần ít nhất hai file để nối audio.")
        command = [self.ffmpeg, "-y"]
        filters: list[str] = []
        labels: list[str] = []
        for index, path in enumerate(parts):
            command += ["-i", str(path)]
            label = f"a{index}"
            labels.append(f"[{label}]")
            filters.append(
                f"[{index}:a:0]aresample=48000,"
                f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[{label}]"
            )
        filters.append(f"{''.join(labels)}concat=n={len(parts)}:v=0:a=1[outa]")
        command += [
            "-filter_complex", ";".join(filters), "-map", "[outa]",
            "-c:a", "aac", "-b:a", "192k", str(destination),
        ]
        self._run(command, expected_duration)

    def mux_narration(self, video: Path, audio: Path, destination: Path, duration: float) -> None:
        command = [
            self.ffmpeg, "-y", "-i", str(video), "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-shortest", "-t", f"{duration:.3f}",
            "-movflags", "+faststart", str(destination),
        ]
        self._run(command, duration)

    def mux_looped_narration(self, video: Path, audio: Path, destination: Path, duration: float) -> None:
        command = [
            self.ffmpeg, "-y", "-stream_loop", "-1", "-i", str(video), "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-shortest", "-t", f"{duration:.3f}",
            "-movflags", "+faststart", str(destination),
        ]
        self._run(command, duration)

    def stop(self) -> None:
        self.stop_event.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()


class VideoLoopApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Mini Tool Loop Video")
        self.geometry("1040x720")
        self.minsize(820, 620)
        self.configure(bg="#101914")
        self.option_add("*Font", "{Segoe UI} 10")
        self.files: list[Path] = []
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.engine: FFmpegLoopEngine | None = None
        self._style()
        self._build()
        self.after(150, self._poll)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#101914", foreground="#f2eadb", fieldbackground="#1d3026")
        style.configure("TFrame", background="#101914")
        style.configure("Card.TFrame", background="#18251e")
        style.configure("TLabel", background="#101914", foreground="#f2eadb")
        style.configure("Card.TLabel", background="#18251e", foreground="#f2eadb")
        style.configure("Title.TLabel", font=("Georgia", 22, "bold"), foreground="#f4c95d")
        style.configure("Accent.TButton", background="#f4c95d", foreground="#101914", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#ffe08a")])

    def _build(self) -> None:
        header = ttk.Frame(self, padding=(20, 16))
        header.pack(fill="x")
        ttk.Label(header, text="MINI TOOL LOOP VIDEO", style="Title.TLabel").pack(side="left")
        self.status = tk.StringVar(value="Sẵn sàng")
        ttk.Label(header, textvariable=self.status).pack(side="right")

        body = ttk.Frame(self, padding=(18, 0, 18, 18))
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, style="Card.TFrame", padding=14)
        left.pack(side="left", fill="y", padx=(0, 12))
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.mode = tk.StringVar(value="one_to_one")
        ttk.Label(left, text="Chế độ xuất", style="Card.TLabel", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Radiobutton(left, text="1-1: mỗi video thành một video dài", variable=self.mode, value="one_to_one").pack(anchor="w", pady=(8, 2))
        ttk.Radiobutton(left, text="1-nhiều: ghép tất cả thành một video", variable=self.mode, value="many_to_one").pack(anchor="w", pady=2)

        self.hours = tk.IntVar(value=1)
        self.minutes = tk.IntVar(value=0)
        self.fade = tk.DoubleVar(value=0.7)
        self.bitrate = tk.DoubleVar(value=10.0)
        self.use_gpu = tk.BooleanVar(value=True)
        for label, variable, start, end, step in (
            ("Số giờ", self.hours, 0, 24, 1),
            ("Số phút", self.minutes, 0, 59, 1),
            ("Hòa trộn (giây)", self.fade, 0.1, 3.0, 0.1),
            ("Bitrate mục tiêu (Mbps)", self.bitrate, 1.0, 100.0, 0.5),
        ):
            ttk.Label(left, text=label, style="Card.TLabel").pack(anchor="w", pady=(12, 3))
            ttk.Spinbox(left, from_=start, to=end, increment=step, textvariable=variable, width=22).pack(fill="x")

        ttk.Checkbutton(
            left, text="Dùng GPU NVIDIA (NVENC)", variable=self.use_gpu,
        ).pack(anchor="w", pady=(14, 0))
        ttk.Label(
            left, text="RTX 3060: mã hóa H.264 bằng GPU", style="Card.TLabel",
            foreground="#8bd49c",
        ).pack(anchor="w", pady=(2, 0))
        self.size_estimate = tk.StringVar()
        ttk.Label(left, textvariable=self.size_estimate, style="Card.TLabel", foreground="#f4c95d").pack(anchor="w", pady=(8, 0))
        for variable in (self.hours, self.minutes, self.bitrate):
            variable.trace_add("write", self._update_size_estimate)
        self._update_size_estimate()

        self.output_dir = tk.StringVar(value=str(Path.home() / "Videos" / "Looped"))
        ttk.Label(left, text="Thư mục xuất", style="Card.TLabel").pack(anchor="w", pady=(12, 3))
        ttk.Entry(left, textvariable=self.output_dir, width=34).pack(fill="x")
        ttk.Button(left, text="Chọn thư mục xuất", command=self._choose_output).pack(fill="x", pady=5)
        self.start_button = ttk.Button(left, text="BẮT ĐẦU LOOP", style="Accent.TButton", command=self._start)
        self.start_button.pack(fill="x", pady=(18, 5))
        ttk.Button(left, text="Dừng", command=self._stop).pack(fill="x")

        actions = ttk.Frame(right)
        actions.pack(fill="x")
        ttk.Button(actions, text="Thêm video", command=self._add_files).pack(side="left", padx=(0, 5))
        ttk.Button(actions, text="Nạp cả thư mục", command=self._add_folder).pack(side="left", padx=5)
        ttk.Button(actions, text="Xóa danh sách", command=self._clear).pack(side="left", padx=5)
        self.file_list = tk.Listbox(right, height=11, bg="#18251e", fg="#f2eadb", selectbackground="#b97435", relief="flat")
        self.file_list.pack(fill="x", pady=10)
        self.progress = ttk.Progressbar(right, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 8))
        self.log = tk.Text(right, bg="#0b110e", fg="#b9d8c2", insertbackground="white", relief="flat", state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Chọn video", filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v")])
        self._append([Path(path) for path in paths])

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Chọn thư mục video")
        if folder:
            self._append(sorted(path for path in Path(folder).iterdir() if path.suffix.lower() in VIDEO_EXTENSIONS))

    def _append(self, paths: list[Path]) -> None:
        existing = {path.resolve() for path in self.files}
        for path in paths:
            if path.resolve() not in existing:
                self.files.append(path)
                existing.add(path.resolve())
                self.file_list.insert("end", str(path))
        self.status.set(f"Đã chọn {len(self.files)} video")

    def _update_size_estimate(self, *_args) -> None:
        try:
            seconds = self.hours.get() * 3600 + self.minutes.get() * 60
            size_gb = self.bitrate.get() * seconds / 8 / 1000
            self.size_estimate.set(f"Ước tính mỗi video: ~{size_gb:.2f} GB")
        except (tk.TclError, ValueError):
            self.size_estimate.set("Ước tính mỗi video: --")

    def _clear(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.files.clear()
        self.file_list.delete(0, "end")
        self.progress["value"] = 0

    def _choose_output(self) -> None:
        folder = filedialog.askdirectory(title="Chọn thư mục xuất")
        if folder:
            self.output_dir.set(folder)

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self.files:
            messagebox.showwarning("Thiếu video", "Hãy chọn ít nhất một video.")
            return
        target = self.hours.get() * 3600 + self.minutes.get() * 60
        if target <= 0:
            messagebox.showwarning("Thời lượng", "Tổng thời lượng phải lớn hơn 0 phút.")
            return
        bitrate = self.bitrate.get()
        if bitrate < 1:
            messagebox.showwarning("Bitrate", "Bitrate phải từ 1 Mbps trở lên.")
            return
        ffmpeg, ffprobe = find_ffmpeg_tools()
        if not ffmpeg or not ffprobe:
            messagebox.showerror("Thiếu FFmpeg", "Không tìm thấy ffmpeg/ffprobe trong PATH. Hãy cài FFmpeg rồi mở lại tool.")
            return
        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        self.progress.configure(maximum=len(self.files) if self.mode.get() == "one_to_one" else 1, value=0)
        settings = (self.mode.get(), self.fade.get(), self.use_gpu.get(), bitrate)
        self.worker = threading.Thread(target=self._work, args=(ffmpeg, ffprobe, target, settings), daemon=True)
        self.worker.start()

    def _work(
        self, ffmpeg: str, ffprobe: str, target: int,
        settings: tuple[str, float, bool, float],
    ) -> None:
        mode, fade, use_gpu, bitrate = settings
        output_dir = Path(self.output_dir.get()).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        self.engine = FFmpegLoopEngine(
            ffmpeg, ffprobe, lambda value: self.events.put(("log", value)),
            self.stop_event, use_gpu=use_gpu, bitrate_mbps=bitrate,
        )
        encoder = "NVIDIA H.264 NVENC (GPU)" if use_gpu else "libx264 (CPU)"
        self.events.put(("log", f"Encoder: {encoder}; bitrate mục tiêu: {bitrate:g} Mbps"))
        try:
            with tempfile.TemporaryDirectory(prefix="video_loop_") as temp_name:
                temp = Path(temp_name)
                if mode == "one_to_one":
                    for index, source in enumerate(self.files, 1):
                        self.events.put(("status", f"Đang xử lý {index}/{len(self.files)}: {source.name}"))
                        cycle = temp / f"cycle_{index}.mp4"
                        self.engine.make_single_cycle(source, cycle, fade)
                        output = output_dir / f"{source.stem}_loop_{format_seconds(target).replace(':', '-')}.mp4"
                        self.engine.repeat_cycle(cycle, output, target)
                        self.events.put(("progress", index))
                        self.events.put(("log", f"HOÀN TẤT: {output}"))
                else:
                    self.events.put(("status", f"Đang hòa trộn {len(self.files)} video..."))
                    cycle = temp / "multi_cycle.mp4"
                    self.engine.make_multi_cycle(self.files, cycle, fade)
                    output = output_dir / f"mixed_{len(self.files)}_videos_loop_{format_seconds(target).replace(':', '-')}.mp4"
                    self.engine.repeat_cycle(cycle, output, target)
                    self.events.put(("progress", 1))
                    self.events.put(("log", f"HOÀN TẤT: {output}"))
            self.events.put(("done", str(output_dir)))
        except InterruptedError as error:
            self.events.put(("stopped", str(error)))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _stop(self) -> None:
        if self.engine:
            self.engine.stop()
        self.status.set("Đang dừng...")

    def _poll(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", str(value) + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "status":
                    self.status.set(str(value))
                elif kind == "progress":
                    self.progress["value"] = int(value)
                elif kind == "done":
                    self.status.set("Hoàn tất")
                    self.start_button.configure(state="normal")
                    messagebox.showinfo("Hoàn tất", f"Video đã lưu tại:\n{value}")
                elif kind == "stopped":
                    self.status.set("Đã dừng")
                    self.start_button.configure(state="normal")
                elif kind == "error":
                    self.status.set("Có lỗi")
                    self.start_button.configure(state="normal")
                    messagebox.showerror("Lỗi xử lý", str(value))
        except queue.Empty:
            pass
        self.after(150, self._poll)


if __name__ == "__main__":
    VideoLoopApp().mainloop()
