from __future__ import annotations

import json
import os
import queue
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.style import Colors, ThemeDefinition

from audio_full_tool import AUDIO_EXTENSIONS
from video_loop_tool import FFmpegLoopEngine, VIDEO_EXTENSIONS, find_ffmpeg_tools, format_seconds


LIGHT = {
    "bg": "#EDF3F0", "surface": "#FFFFFF", "field": "#DDE9E3",
    "text": "#16231D", "muted": "#5E7168", "border": "#C7D6CF",
    "accent": "#16795B", "accent_text": "#FFFFFF", "warning": "#D97706",
    "success": "#16795B", "log": "#F7FAF8",
}
DARK = {
    "bg": "#101713", "surface": "#18221D", "field": "#243229",
    "text": "#F1F7F3", "muted": "#A5B7AD", "border": "#35473D",
    "accent": "#42C795", "accent_text": "#07120D", "warning": "#F59E0B",
    "success": "#6DE2B1", "log": "#0B100D",
}


def mint_theme(name: str, colors: dict[str, str], mode: str) -> ThemeDefinition:
    return ThemeDefinition(
        name=name,
        mode=mode,
        colors=Colors(
            primary=colors["accent"],
            secondary=colors["muted"],
            success=colors["success"],
            info="#2689A8" if mode == "light" else "#55B7D1",
            warning=colors["warning"],
            danger="#C2413B" if mode == "light" else "#F07972",
            light=colors["surface"],
            dark=colors["text"],
            bg=colors["bg"],
            fg=colors["text"],
            selectbg=colors["accent"],
            selectfg=colors["accent_text"],
            border=colors["border"],
            inputfg=colors["text"],
            inputbg=colors["field"],
            active=colors["border"],
        ),
    )


class SettingsStore:
    def __init__(self) -> None:
        appdata = Path(os.environ.get("APPDATA", Path.home()))
        self.path = appdata / "LoopVideoSuite" / "settings.json"

    def load_theme(self) -> str:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8")).get("theme", "light")
            return value if value in {"light", "dark"} else "light"
        except (OSError, ValueError, TypeError):
            return "light"

    def save_theme(self, theme: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"theme": theme}, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.path)


class ProcessingTab(ttk.Frame):
    def __init__(self, master: tk.Misc, app: "LoopVideoSuiteApp") -> None:
        super().__init__(master, style="App.TFrame", padding=18)
        self.app = app
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.engine: FFmpegLoopEngine | None = None
        self.status = tk.StringVar(value="Sẵn sàng")
        self.after(150, self._poll_events)

    def is_running(self) -> bool:
        return bool(self.worker and self.worker.is_alive())

    def stop(self) -> None:
        if self.engine:
            self.engine.stop()
        self.status.set("Đang dừng...")

    def apply_native_theme(self, colors: dict[str, str]) -> None:
        raise NotImplementedError

    def _append_log(self, value: object) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", str(value) + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _finish(self, status: str) -> None:
        self.status.set(status)
        self.start_button.configure(state="normal")
        self.app.release_job(self)

    def _poll_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self._append_log(value)
                elif kind == "status":
                    self.status.set(str(value))
                    self.app.update_tab_status(self)
                elif kind == "progress":
                    self.progress["value"] = int(value)
                    self.app.update_tab_status(self)
                elif kind == "done":
                    self._finish("Hoàn tất")
                    messagebox.showinfo("Hoàn tất", f"Đã lưu kết quả tại:\n{value}")
                elif kind == "stopped":
                    self._finish("Đã dừng")
                elif kind == "error":
                    self._finish("Có lỗi")
                    messagebox.showerror("Lỗi xử lý", str(value))
        except queue.Empty:
            pass
        self.after(150, self._poll_events)


class LoopTab(ProcessingTab):
    def __init__(self, master: tk.Misc, app: "LoopVideoSuiteApp") -> None:
        super().__init__(master, app)
        self.files: list[Path] = []
        self.mode = tk.StringVar(value="one_to_one")
        self.hours = tk.IntVar(value=1)
        self.minutes = tk.IntVar(value=0)
        self.fade = tk.DoubleVar(value=0.7)
        self.bitrate = tk.DoubleVar(value=10.0)
        self.use_gpu = tk.BooleanVar(value=True)
        self.output_dir = tk.StringVar(value=str(Path.home() / "Videos" / "Looped"))
        self.size_estimate = tk.StringVar()
        self._build()
        for variable in (self.hours, self.minutes, self.bitrate):
            variable.trace_add("write", self._update_estimate)
        self._update_estimate()

    def _build(self) -> None:
        left = ttk.Frame(self, style="Panel.TFrame", padding=20, width=360)
        right = ttk.Frame(self, style="Panel.TFrame", padding=20)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="THIẾT LẬP LOOP", style="Section.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(left, text="Chế độ xuất", style="Panel.TLabel").pack(anchor="w", pady=(5, 4))
        ttk.Combobox(
            left, textvariable=self.mode,
            values=("one_to_one", "many_to_one"), state="readonly",
        ).pack(fill="x", ipady=7)
        row = ttk.Frame(left, style="Panel.TFrame"); row.pack(fill="x", pady=(12, 0))
        self._spin(row, "Giờ", self.hours, 0, 24, side="left")
        self._spin(row, "Phút", self.minutes, 0, 59, side="left", padx=(10, 0))
        row2 = ttk.Frame(left, style="Panel.TFrame"); row2.pack(fill="x", pady=(12, 0))
        self._spin(row2, "Hòa trộn (giây)", self.fade, .1, 3, .1, "left")
        self._spin(row2, "Bitrate (Mbps)", self.bitrate, 1, 100, .5, "left", (10, 0))
        ttk.Checkbutton(left, text="Dùng GPU NVIDIA NVENC", variable=self.use_gpu, bootstyle="success-round-toggle").pack(anchor="w", pady=(18, 8))
        ttk.Label(left, textvariable=self.size_estimate, style="Estimate.TLabel").pack(fill="x", pady=8, ipady=10)
        ttk.Label(left, text="Thư mục xuất", style="Panel.TLabel").pack(anchor="w", pady=(10, 4))
        ttk.Entry(left, textvariable=self.output_dir).pack(fill="x", ipady=7)
        ttk.Button(left, text="Chọn thư mục xuất", command=self._choose_output, bootstyle="secondary-outline").pack(fill="x", pady=(6, 0), ipady=4)
        self.start_button = ttk.Button(left, text="BẮT ĐẦU LOOP", style="Primary.TButton", command=self._start, bootstyle="success")
        self.start_button.pack(fill="x", pady=(20, 7), ipady=8)
        ttk.Button(left, text="DỪNG TÁC VỤ", command=self.stop, bootstyle="danger-outline").pack(fill="x", ipady=6)

        header = ttk.Frame(right, style="Panel.TFrame"); header.pack(fill="x")
        ttk.Label(header, text="Danh sách video", style="Heading.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.status, style="Status.TLabel").pack(side="right")
        actions = ttk.Frame(right, style="Panel.TFrame"); actions.pack(fill="x", pady=(14, 10))
        ttk.Button(actions, text="+ Thêm video", style="Primary.TButton", command=self._add_files, bootstyle="success").pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="Nạp thư mục", command=self._add_folder, bootstyle="secondary-outline").pack(side="left", padx=7)
        ttk.Button(actions, text="Xóa danh sách", command=self._clear, bootstyle="danger-outline").pack(side="left", padx=7)
        self.file_list = tk.Listbox(right, relief="flat", highlightthickness=1, height=12)
        self.file_list.pack(fill="both", expand=True, pady=(0, 12))
        self.progress = ttk.Progressbar(right, mode="determinate", bootstyle="success-striped")
        self.progress.pack(fill="x", pady=(0, 10), ipady=3)
        self.log = tk.Text(right, height=8, relief="flat", state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

    def _spin(self, parent, label, variable, start, end, increment=1, side="left", padx=0) -> None:
        box = ttk.Frame(parent, style="Panel.TFrame"); box.pack(side=side, fill="x", expand=True, padx=padx)
        ttk.Label(box, text=label, style="Panel.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Spinbox(box, from_=start, to=end, increment=increment, textvariable=variable).pack(fill="x", ipady=7)

    def apply_native_theme(self, c: dict[str, str]) -> None:
        self.file_list.configure(bg=c["surface"], fg=c["text"], selectbackground=c["accent"], selectforeground=c["accent_text"], highlightbackground=c["border"])
        self.log.configure(bg=c["log"], fg=c["muted"], insertbackground=c["text"])

    def _update_estimate(self, *_args) -> None:
        try:
            seconds = self.hours.get() * 3600 + self.minutes.get() * 60
            self.size_estimate.set(f"Ước tính mỗi video  ~{self.bitrate.get() * seconds / 8 / 1000:.2f} GB")
        except tk.TclError:
            self.size_estimate.set("Ước tính mỗi video  --")

    def _choose_output(self) -> None:
        value = filedialog.askdirectory(title="Chọn thư mục xuất")
        if value: self.output_dir.set(value)

    def _add_files(self) -> None:
        values = filedialog.askopenfilenames(title="Chọn video", filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v")])
        self._append_files([Path(value) for value in values])

    def _add_folder(self) -> None:
        value = filedialog.askdirectory(title="Chọn thư mục video")
        if value: self._append_files(sorted(p for p in Path(value).iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS))

    def _append_files(self, paths: list[Path]) -> None:
        known = {p.resolve() for p in self.files}
        for path in paths:
            if path.resolve() not in known:
                self.files.append(path); known.add(path.resolve()); self.file_list.insert("end", str(path))
        self.status.set(f"Đã chọn {len(self.files)} video")

    def _clear(self) -> None:
        if self.is_running(): return
        self.files.clear(); self.file_list.delete(0, "end"); self.progress["value"] = 0

    def _start(self) -> None:
        if not self.app.acquire_job(self): return
        try:
            target = self.hours.get() * 3600 + self.minutes.get() * 60
            if not self.files: raise ValueError("Hãy chọn ít nhất một video.")
            if target <= 0: raise ValueError("Thời lượng đầu ra phải lớn hơn 0.")
            if self.bitrate.get() < 1: raise ValueError("Bitrate phải từ 1 Mbps.")
            ffmpeg, ffprobe = find_ffmpeg_tools()
            if not ffmpeg or not ffprobe: raise ValueError("Không tìm thấy FFmpeg/ffprobe.")
        except (ValueError, tk.TclError) as error:
            self.app.release_job(self); messagebox.showwarning("Chưa thể bắt đầu", str(error)); return
        self.stop_event.clear(); self.start_button.configure(state="disabled")
        maximum = len(self.files) if self.mode.get() == "one_to_one" else 1
        self.progress.configure(maximum=maximum, value=0)
        settings = (self.mode.get(), self.fade.get(), self.use_gpu.get(), self.bitrate.get())
        self.worker = threading.Thread(target=self._work, args=(ffmpeg, ffprobe, target, settings), daemon=True); self.worker.start()

    def _work(self, ffmpeg: str, ffprobe: str, target: int, settings: tuple[str, float, bool, float]) -> None:
        mode, fade, use_gpu, bitrate = settings
        output_dir = Path(self.output_dir.get()).expanduser(); output_dir.mkdir(parents=True, exist_ok=True)
        self.engine = FFmpegLoopEngine(ffmpeg, ffprobe, lambda v: self.events.put(("log", v)), self.stop_event, use_gpu, bitrate)
        try:
            with tempfile.TemporaryDirectory(prefix="video_loop_") as name:
                temp = Path(name)
                if mode == "one_to_one":
                    for index, source in enumerate(self.files, 1):
                        self.events.put(("status", f"Đang xử lý {index}/{len(self.files)} · {source.name}"))
                        cycle = temp / f"cycle_{index}.mp4"; self.engine.make_single_cycle(source, cycle, fade)
                        output = output_dir / f"{source.stem}_loop_{format_seconds(target).replace(':', '-')}.mp4"
                        self.engine.repeat_cycle(cycle, output, target); self.events.put(("progress", index)); self.events.put(("log", f"HOÀN TẤT: {output}"))
                else:
                    self.events.put(("status", f"Đang hòa trộn {len(self.files)} video"))
                    cycle = temp / "multi_cycle.mp4"; self.engine.make_multi_cycle(self.files, cycle, fade)
                    output = output_dir / f"mixed_{len(self.files)}_videos_loop_{format_seconds(target).replace(':', '-')}.mp4"
                    self.engine.repeat_cycle(cycle, output, target); self.events.put(("progress", 1)); self.events.put(("log", f"HOÀN TẤT: {output}"))
            self.events.put(("done", str(output_dir)))
        except InterruptedError as error: self.events.put(("stopped", str(error)))
        except Exception as error: self.events.put(("error", str(error)))


class AudioTab(ProcessingTab):
    def __init__(self, master: tk.Misc, app: "LoopVideoSuiteApp") -> None:
        super().__init__(master, app)
        self.audio_files: list[Path] = []; self.video_files: list[Path] = []
        self.video_dir = tk.StringVar(); self.intro_dir = tk.StringVar(); self.default_intro = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path.home() / "Videos" / "Full"))
        self.fade = tk.DoubleVar(value=.7); self.bitrate = tk.DoubleVar(value=10.0); self.use_gpu = tk.BooleanVar(value=True)
        self._build()

    def _build(self) -> None:
        left = ttk.Frame(self, style="Panel.TFrame", padding=20, width=360); left.pack(side="left", fill="y", padx=(0, 14)); left.pack_propagate(False)
        right = ttk.Frame(self, style="Panel.TFrame", padding=20); right.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="AUDIO + VIDEO + INTRO", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self._path(left, "Video minh họa", self.video_dir, self._choose_video_dir)
        self._path(left, "Intro theo kênh", self.intro_dir, self._choose_intro_dir)
        self._path(left, "Intro mặc định", self.default_intro, self._choose_default_intro)
        self._path(left, "Thư mục xuất", self.output_dir, self._choose_output)
        row = ttk.Frame(left, style="Panel.TFrame"); row.pack(fill="x", pady=(12, 0))
        self._spin(row, "Hòa trộn", self.fade, .1, 3, .1, "left")
        self._spin(row, "Bitrate", self.bitrate, 1, 100, .5, "left", (10, 0))
        ttk.Checkbutton(left, text="Dùng GPU NVIDIA NVENC", variable=self.use_gpu, bootstyle="success-round-toggle").pack(anchor="w", pady=(17, 5))
        ttk.Label(left, text="Tự nhận intro theo thư mục kênh, sau đó loop video minh họa đến hết lời thoại.", style="Help.TLabel", wraplength=310).pack(fill="x", pady=(8, 4))
        self.start_button = ttk.Button(left, text="TẠO VIDEO _FULL", style="Primary.TButton", command=self._start, bootstyle="success"); self.start_button.pack(fill="x", pady=(20, 7), ipady=8)
        ttk.Button(left, text="DỪNG TÁC VỤ", command=self.stop, bootstyle="danger-outline").pack(fill="x", ipady=6)
        header = ttk.Frame(right, style="Panel.TFrame"); header.pack(fill="x")
        ttk.Label(header, text="Batch audio lời thoại", style="Heading.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.status, style="Status.TLabel").pack(side="right")
        actions = ttk.Frame(right, style="Panel.TFrame"); actions.pack(fill="x", pady=(14, 10))
        ttk.Button(actions, text="+ Thêm audio", style="Primary.TButton", command=self._add_audio, bootstyle="success").pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="Nạp thư mục audio", command=self._add_audio_folder, bootstyle="secondary-outline").pack(side="left", padx=7)
        ttk.Button(actions, text="Xóa danh sách", command=self._clear, bootstyle="danger-outline").pack(side="left", padx=7)
        self.audio_list = tk.Listbox(right, relief="flat", highlightthickness=1, height=12); self.audio_list.pack(fill="both", expand=True, pady=(0, 12))
        self.progress = ttk.Progressbar(right, mode="determinate", bootstyle="success-striped"); self.progress.pack(fill="x", pady=(0, 10), ipady=3)
        self.log = tk.Text(right, height=8, relief="flat", state="disabled", wrap="word"); self.log.pack(fill="both", expand=True)

    def _path(self, parent, label, variable, command) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").pack(anchor="w", pady=(9, 4))
        row = ttk.Frame(parent, style="Panel.TFrame"); row.pack(fill="x")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True, ipady=7)
        ttk.Button(row, text="Chọn", command=command, bootstyle="secondary-outline").pack(side="left", padx=(6, 0), ipady=4)

    def _spin(self, parent, label, variable, start, end, increment=1, side="left", padx=0) -> None:
        box = ttk.Frame(parent, style="Panel.TFrame"); box.pack(side=side, fill="x", expand=True, padx=padx)
        ttk.Label(box, text=label, style="Panel.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Spinbox(box, from_=start, to=end, increment=increment, textvariable=variable).pack(fill="x", ipady=7)

    def apply_native_theme(self, c: dict[str, str]) -> None:
        self.audio_list.configure(bg=c["surface"], fg=c["text"], selectbackground=c["accent"], selectforeground=c["accent_text"], highlightbackground=c["border"])
        self.log.configure(bg=c["log"], fg=c["muted"], insertbackground=c["text"])

    def _choose_video_dir(self):
        value = filedialog.askdirectory(title="Chọn thư mục video minh họa"); self.video_dir.set(value or self.video_dir.get())
    def _choose_intro_dir(self):
        value = filedialog.askdirectory(title="Chọn thư mục intro theo kênh"); self.intro_dir.set(value or self.intro_dir.get())
    def _choose_default_intro(self):
        value = filedialog.askopenfilename(title="Chọn intro mặc định", filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v")]); self.default_intro.set(value or self.default_intro.get())
    def _choose_output(self):
        value = filedialog.askdirectory(title="Chọn thư mục xuất"); self.output_dir.set(value or self.output_dir.get())
    def _add_audio(self):
        values = filedialog.askopenfilenames(title="Chọn audio", filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus")]); self._append_audio([Path(v) for v in values])
    def _add_audio_folder(self):
        value = filedialog.askdirectory(title="Chọn thư mục audio")
        if value: self._append_audio(sorted(p for p in Path(value).rglob("*") if p.suffix.lower() in AUDIO_EXTENSIONS))
    def _append_audio(self, paths: list[Path]):
        known = {p.resolve() for p in self.audio_files}
        for path in paths:
            if path.resolve() not in known: self.audio_files.append(path); known.add(path.resolve()); self.audio_list.insert("end", str(path))
        self.status.set(f"Đã chọn {len(self.audio_files)} audio")
    def _clear(self):
        if self.is_running(): return
        self.audio_files.clear(); self.audio_list.delete(0, "end"); self.progress["value"] = 0

    @staticmethod
    def find_intro(audio: Path, intros: dict[str, Path], default: Path | None) -> Path | None:
        channel = audio.parent.name.casefold()
        if channel in intros: return intros[channel]
        matches = [(name, path) for name, path in intros.items() if audio.stem.casefold().startswith(name)]
        return max(matches, key=lambda item: len(item[0]))[1] if matches else default

    def _start(self):
        if not self.app.acquire_job(self): return
        try:
            video_dir = Path(self.video_dir.get())
            if not self.audio_files: raise ValueError("Hãy chọn ít nhất một file audio.")
            if not video_dir.is_dir(): raise ValueError("Hãy chọn thư mục video minh họa.")
            videos = sorted(p for p in video_dir.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS)
            if not videos: raise ValueError("Thư mục không có video minh họa hợp lệ.")
            ffmpeg, ffprobe = find_ffmpeg_tools()
            if not ffmpeg or not ffprobe: raise ValueError("Không tìm thấy FFmpeg/ffprobe.")
        except (ValueError, tk.TclError) as error:
            self.app.release_job(self); messagebox.showwarning("Chưa thể bắt đầu", str(error)); return
        self.video_files = videos; self.stop_event.clear(); self.start_button.configure(state="disabled"); self.progress.configure(maximum=len(self.audio_files), value=0)
        settings = (self.fade.get(), self.bitrate.get(), self.use_gpu.get())
        self.worker = threading.Thread(target=self._work, args=(ffmpeg, ffprobe, settings), daemon=True); self.worker.start()

    def _work(self, ffmpeg: str, ffprobe: str, settings: tuple[float, float, bool]):
        fade, bitrate, use_gpu = settings; output_dir = Path(self.output_dir.get()).expanduser(); output_dir.mkdir(parents=True, exist_ok=True)
        intro_root = Path(self.intro_dir.get()) if self.intro_dir.get() else None
        intros = {p.stem.casefold(): p for p in (intro_root.iterdir() if intro_root and intro_root.is_dir() else []) if p.suffix.lower() in VIDEO_EXTENSIONS}
        default = Path(self.default_intro.get()) if self.default_intro.get() else None
        if default and not default.is_file(): default = None
        self.engine = FFmpegLoopEngine(ffmpeg, ffprobe, lambda v: self.events.put(("log", v)), self.stop_event, use_gpu, bitrate)
        try:
            with tempfile.TemporaryDirectory(prefix="audio_full_") as name:
                temp = Path(name); cycle = temp / "illustration_cycle.mp4"
                self.events.put(("status", f"Đang tạo chu kỳ từ {len(self.video_files)} video"))
                (self.engine.make_single_cycle(self.video_files[0], cycle, fade) if len(self.video_files) == 1 else self.engine.make_multi_cycle(self.video_files, cycle, fade))
                normalized: dict[Path, tuple[Path, float]] = {}
                for index, audio in enumerate(self.audio_files, 1):
                    duration = self.engine.duration(audio); intro = self.find_intro(audio, intros, default)
                    self.events.put(("status", f"{index}/{len(self.audio_files)} · {audio.name}")); parts: list[Path] = []; intro_duration = 0.0
                    if intro:
                        if intro not in normalized:
                            target = temp / f"intro_{len(normalized)}.mp4"; normalized[intro] = (target, self.engine.normalize_intro(intro, target, self.engine.duration(intro)))
                        intro_file, intro_duration = normalized[intro]; intro_duration = min(intro_duration, duration); parts.append(intro_file)
                    remaining = max(0.0, duration - intro_duration)
                    if remaining > .02:
                        loop_part = temp / f"loop_{index}.mp4"; self.engine.repeat_cycle(cycle, loop_part, remaining); parts.append(loop_part)
                    visual = parts[0] if len(parts) == 1 else temp / f"visual_{index}.mp4"
                    if len(parts) > 1: self.engine.concat_video_parts(parts, visual)
                    channel = output_dir / audio.parent.name; channel.mkdir(parents=True, exist_ok=True); output = channel / f"{audio.stem}_FULL.mp4"
                    self.engine.mux_narration(visual, audio, output, duration); self.events.put(("progress", index)); self.events.put(("log", f"HOÀN TẤT: {output}"))
                    if remaining > .02: loop_part.unlink(missing_ok=True)
                    if visual.parent == temp and visual.name.startswith("visual_"): visual.unlink(missing_ok=True)
            self.events.put(("done", str(output_dir)))
        except InterruptedError as error: self.events.put(("stopped", str(error)))
        except Exception as error: self.events.put(("error", str(error)))


def discover_audio_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    unique: dict[Path, Path] = {}
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
            unique.setdefault(path.resolve(), path)
    return sorted(unique.values(), key=lambda path: str(path).casefold())


def batch_percent(completed: int, failed: int, current_percent: float, total: int) -> float:
    if total <= 0:
        return 0.0
    return max(0.0, min(100.0, (completed + failed + current_percent / 100) / total * 100))


class EnhancedAudioTab(ProcessingTab):
    LOG_LINE_LIMIT = 10_000

    def __init__(self, master: tk.Misc, app: "LoopVideoSuiteApp") -> None:
        super().__init__(master, app)
        self.audio_files: list[Path] = []
        self.video_files: list[Path] = []
        self.row_ids: dict[Path, str] = {}
        self.preview_data: dict[Path, tuple[float | None, Path | None]] = {}
        self.video_dir = tk.StringVar()
        self.intro_dir = tk.StringVar()
        self.default_intro = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path.home() / "Videos" / "Full"))
        self.fade = tk.DoubleVar(value=.7)
        self.bitrate = tk.DoubleVar(value=10.0)
        self.use_gpu = tk.BooleanVar(value=True)
        self.total_count = tk.IntVar(value=0)
        self.completed_count = tk.IntVar(value=0)
        self.failed_count = tk.IntVar(value=0)
        self.waiting_count = tk.IntVar(value=0)
        self.current_progress = tk.DoubleVar(value=0)
        self.batch_progress = tk.DoubleVar(value=0)
        self.current_progress_text = tk.StringVar(value="File hiện tại: 0%")
        self.batch_progress_text = tk.StringVar(value="Toàn batch: 0%")
        self.active_audio: Path | None = None
        self.session_log_path: Path | None = None
        self._build()

    def _build(self) -> None:
        left = ttk.Frame(self, style="Panel.TFrame", padding=20, width=360)
        left.pack(side="left", fill="y", padx=(0, 14)); left.pack_propagate(False)
        right = ttk.Frame(self, style="Panel.TFrame", padding=20)
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="AUDIO + VIDEO + INTRO", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self._path(left, "Video minh họa", self.video_dir, self._choose_video_dir)
        self._path(left, "Intro theo kênh", self.intro_dir, self._choose_intro_dir)
        self._path(left, "Intro mặc định", self.default_intro, self._choose_default_intro)
        self._path(left, "Thư mục xuất", self.output_dir, self._choose_output)
        row = ttk.Frame(left, style="Panel.TFrame"); row.pack(fill="x", pady=(12, 0))
        self._spin(row, "Hòa trộn", self.fade, .1, 3, .1, "left")
        self._spin(row, "Bitrate", self.bitrate, 1, 100, .5, "left", (10, 0))
        ttk.Checkbutton(left, text="Dùng GPU NVIDIA NVENC", variable=self.use_gpu, bootstyle="success-round-toggle").pack(anchor="w", pady=(17, 5))
        ttk.Label(left, text="Quét mọi thư mục con. Intro được xem trước theo tên kênh trước khi chạy.", style="Help.TLabel", wraplength=310).pack(fill="x", pady=(8, 4))
        self.start_button = ttk.Button(left, text="TẠO VIDEO _FULL", command=self._start, bootstyle="success")
        self.start_button.pack(fill="x", pady=(20, 7), ipady=8)
        ttk.Button(left, text="DỪNG TÁC VỤ", command=self.stop, bootstyle="danger-outline").pack(fill="x", ipady=6)

        header = ttk.Frame(right, style="Panel.TFrame"); header.pack(fill="x")
        ttk.Label(header, text="Batch audio lời thoại", style="Heading.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.status, style="Status.TLabel").pack(side="right")
        actions = ttk.Frame(right, style="Panel.TFrame"); actions.pack(fill="x", pady=(12, 8))
        ttk.Button(actions, text="+ Thêm audio", command=self._add_audio, bootstyle="success").pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="Nạp thư mục + thư mục con", command=self._add_audio_folder, bootstyle="secondary-outline").pack(side="left", padx=7)
        ttk.Button(actions, text="Làm mới intro", command=self._refresh_preview, bootstyle="info-outline").pack(side="left", padx=7)
        ttk.Button(actions, text="Xóa danh sách", command=self._clear, bootstyle="danger-outline").pack(side="left", padx=7)

        stats = ttk.Frame(right, style="Panel.TFrame"); stats.pack(fill="x", pady=(0, 8))
        for label, variable, style in (
            ("Tổng", self.total_count, "secondary"), ("Hoàn tất", self.completed_count, "success"),
            ("Thất bại", self.failed_count, "danger"), ("Đang chờ", self.waiting_count, "warning"),
        ):
            card = ttk.LabelFrame(stats, text=label, padding=(14, 6), bootstyle=style)
            card.pack(side="left", fill="x", expand=True, padx=4)
            ttk.Label(card, textvariable=variable, font=("Segoe UI", 15, "bold")).pack()

        columns = ("index", "name", "channel", "duration", "intro", "status", "percent")
        table_wrap = ttk.Frame(right, style="Panel.TFrame"); table_wrap.pack(fill="both", expand=True)
        self.audio_tree = ttk.Treeview(table_wrap, columns=columns, show="headings", height=10, bootstyle="success")
        headings = {"index": "STT", "name": "Audio", "channel": "Kênh / thư mục", "duration": "Thời lượng", "intro": "Intro đã khớp", "status": "Trạng thái", "percent": "%"}
        widths = {"index": 48, "name": 230, "channel": 155, "duration": 85, "intro": 180, "status": 125, "percent": 55}
        for column in columns:
            self.audio_tree.heading(column, text=headings[column]); self.audio_tree.column(column, width=widths[column], anchor="center" if column in {"index", "duration", "status", "percent"} else "w")
        scrollbar = ttk.Scrollbar(table_wrap, orient="vertical", command=self.audio_tree.yview, bootstyle="success-round")
        self.audio_tree.configure(yscrollcommand=scrollbar.set)
        self.audio_tree.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")

        progress_box = ttk.Frame(right, style="Panel.TFrame"); progress_box.pack(fill="x", pady=(10, 6))
        ttk.Label(progress_box, textvariable=self.current_progress_text, style="Panel.TLabel").pack(anchor="w")
        self.current_bar = ttk.Progressbar(progress_box, variable=self.current_progress, maximum=100, bootstyle="info-striped")
        self.current_bar.pack(fill="x", pady=(3, 7), ipady=2)
        ttk.Label(progress_box, textvariable=self.batch_progress_text, style="Panel.TLabel").pack(anchor="w")
        self.progress = ttk.Progressbar(progress_box, variable=self.batch_progress, maximum=100, bootstyle="success-striped")
        self.progress.pack(fill="x", pady=(3, 0), ipady=2)

        self.log_notebook = ttk.Notebook(right, bootstyle="success")
        self.log_notebook.pack(fill="both", expand=True, pady=(8, 0))
        readable_frame = ttk.Frame(self.log_notebook, style="Panel.TFrame", padding=6)
        raw_frame = ttk.Frame(self.log_notebook, style="Panel.TFrame", padding=6)
        self.log_notebook.add(readable_frame, text="Tiến trình")
        self.log_notebook.add(raw_frame, text="FFmpeg Log")
        self.log = tk.Text(readable_frame, height=7, relief="flat", state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)
        raw_actions = ttk.Frame(raw_frame, style="Panel.TFrame"); raw_actions.pack(fill="x", pady=(0, 5))
        ttk.Button(raw_actions, text="Xóa hiển thị", command=self._clear_raw_log, bootstyle="secondary-outline").pack(side="left")
        ttk.Button(raw_actions, text="Lưu log...", command=self._save_log, bootstyle="success-outline").pack(side="left", padx=(7, 0))
        self.raw_log = tk.Text(raw_frame, height=7, relief="flat", state="disabled", wrap="none")
        self.raw_log.pack(fill="both", expand=True)

    def _path(self, parent, label, variable, command) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").pack(anchor="w", pady=(9, 4))
        row = ttk.Frame(parent, style="Panel.TFrame"); row.pack(fill="x")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True, ipady=7)
        ttk.Button(row, text="Chọn", command=command, bootstyle="secondary-outline").pack(side="left", padx=(6, 0), ipady=4)

    def _spin(self, parent, label, variable, start, end, increment=1, side="left", padx=0) -> None:
        box = ttk.Frame(parent, style="Panel.TFrame"); box.pack(side=side, fill="x", expand=True, padx=padx)
        ttk.Label(box, text=label, style="Panel.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Spinbox(box, from_=start, to=end, increment=increment, textvariable=variable).pack(fill="x", ipady=7)

    def apply_native_theme(self, c: dict[str, str]) -> None:
        for widget in (self.log, self.raw_log):
            widget.configure(bg=c["log"], fg=c["muted"], insertbackground=c["text"])

    def _choose_video_dir(self) -> None:
        value = filedialog.askdirectory(title="Chọn thư mục video minh họa")
        if value: self.video_dir.set(value)

    def _choose_intro_dir(self) -> None:
        value = filedialog.askdirectory(title="Chọn thư mục intro theo kênh")
        if value: self.intro_dir.set(value); self._refresh_preview()

    def _choose_default_intro(self) -> None:
        value = filedialog.askopenfilename(title="Chọn intro mặc định", filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v")])
        if value: self.default_intro.set(value); self._refresh_preview()

    def _choose_output(self) -> None:
        value = filedialog.askdirectory(title="Chọn thư mục xuất")
        if value: self.output_dir.set(value)

    def _add_audio(self) -> None:
        values = filedialog.askopenfilenames(title="Chọn audio", filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus")])
        self._append_audio([Path(value) for value in values])

    def _add_audio_folder(self) -> None:
        value = filedialog.askdirectory(title="Chọn thư mục audio gốc")
        if value: self._append_audio(discover_audio_files(Path(value)))

    def _append_audio(self, paths: list[Path]) -> None:
        known = {path.resolve() for path in self.audio_files}
        for path in paths:
            resolved = path.resolve()
            if resolved in known: continue
            self.audio_files.append(path); known.add(resolved)
            row_id = self.audio_tree.insert("", "end", values=(len(self.audio_files), path.name, path.parent.name, "Đang đọc...", "Đang khớp...", "Đang chờ", "0%"))
            self.row_ids[path] = row_id
        self._update_counts(0, 0)
        self.status.set(f"Đã chọn {len(self.audio_files)} audio")
        self._refresh_preview()

    def _intro_map(self) -> tuple[dict[str, Path], Path | None]:
        root = Path(self.intro_dir.get()) if self.intro_dir.get() else None
        intros = {path.stem.casefold(): path for path in (root.rglob("*") if root and root.is_dir() else []) if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS}
        default = Path(self.default_intro.get()) if self.default_intro.get() else None
        return intros, default if default and default.is_file() else None

    @staticmethod
    def find_intro(audio: Path, intros: dict[str, Path], default: Path | None) -> Path | None:
        channel = audio.parent.name.casefold()
        if channel in intros: return intros[channel]
        matches = [(name, path) for name, path in intros.items() if audio.stem.casefold().startswith(name)]
        return max(matches, key=lambda item: len(item[0]))[1] if matches else default

    def _refresh_preview(self) -> None:
        if not self.audio_files or self.is_running(): return
        ffmpeg, ffprobe = find_ffmpeg_tools()
        if not ffprobe: return
        intros, default = self._intro_map(); files = list(self.audio_files)
        threading.Thread(target=self._preview_worker, args=(ffmpeg or "", ffprobe, files, intros, default), daemon=True).start()

    def _preview_worker(self, ffmpeg: str, ffprobe: str, files: list[Path], intros: dict[str, Path], default: Path | None) -> None:
        engine = FFmpegLoopEngine(ffmpeg, ffprobe, lambda _v: None, threading.Event(), False, 10)
        for audio in files:
            try: duration = engine.duration(audio)
            except Exception: duration = None
            self.events.put(("preview", (audio, duration, self.find_intro(audio, intros, default))))

    def _clear(self) -> None:
        if self.is_running(): return
        self.audio_files.clear(); self.row_ids.clear(); self.preview_data.clear()
        for item in self.audio_tree.get_children(): self.audio_tree.delete(item)
        self.current_progress.set(0); self.batch_progress.set(0); self._update_counts(0, 0)

    def _update_counts(self, completed: int, failed: int) -> None:
        total = len(self.audio_files); self.total_count.set(total); self.completed_count.set(completed); self.failed_count.set(failed); self.waiting_count.set(max(0, total - completed - failed - (1 if self.active_audio else 0)))

    def _set_row(self, audio: Path, *, status: str | None = None, percent: float | None = None, duration: float | None = None, intro: Path | None | object = ...) -> None:
        row_id = self.row_ids.get(audio)
        if not row_id: return
        values = list(self.audio_tree.item(row_id, "values"))
        if duration is not None: values[3] = format_seconds(duration)
        if intro is not ...: values[4] = intro.name if isinstance(intro, Path) else "Không có intro"
        if status is not None: values[5] = status
        if percent is not None: values[6] = f"{percent:.0f}%"
        self.audio_tree.item(row_id, values=values)
        self.audio_tree.see(row_id)

    def _clear_raw_log(self) -> None:
        self.raw_log.configure(state="normal"); self.raw_log.delete("1.0", "end"); self.raw_log.configure(state="disabled")

    def _save_log(self) -> None:
        if not self.session_log_path or not self.session_log_path.exists():
            messagebox.showinfo("Chưa có log", "Chưa có phiên xử lý để lưu log."); return
        value = filedialog.asksaveasfilename(title="Lưu FFmpeg log", defaultextension=".log", filetypes=[("Log UTF-8", "*.log"), ("Text", "*.txt")])
        if value: Path(value).write_text(self.session_log_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

    def _start(self) -> None:
        if not self.app.acquire_job(self): return
        try:
            video_dir = Path(self.video_dir.get())
            if not self.audio_files: raise ValueError("Hãy chọn ít nhất một file audio.")
            if not video_dir.is_dir(): raise ValueError("Hãy chọn thư mục video minh họa.")
            videos = sorted(path for path in video_dir.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS)
            if not videos: raise ValueError("Thư mục không có video minh họa hợp lệ.")
            ffmpeg, ffprobe = find_ffmpeg_tools()
            if not ffmpeg or not ffprobe: raise ValueError("Không tìm thấy FFmpeg/ffprobe.")
        except (ValueError, tk.TclError) as error:
            self.app.release_job(self); messagebox.showwarning("Chưa thể bắt đầu", str(error)); return
        self.video_files = videos; self.stop_event.clear(); self.start_button.configure(state="disabled")
        self.completed_count.set(0); self.failed_count.set(0); self.active_audio = None; self._update_counts(0, 0)
        self.current_progress.set(0); self.batch_progress.set(0)
        log_dir = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "LoopVideoSuite" / "logs"; log_dir.mkdir(parents=True, exist_ok=True)
        self.session_log_path = log_dir / f"audio-full-{time.strftime('%Y%m%d-%H%M%S')}.log"
        settings = (self.fade.get(), self.bitrate.get(), self.use_gpu.get())
        self.worker = threading.Thread(target=self._work, args=(ffmpeg, ffprobe, settings), daemon=True); self.worker.start()

    def _work(self, ffmpeg: str, ffprobe: str, settings: tuple[float, float, bool]) -> None:
        fade, bitrate, use_gpu = settings; output_dir = Path(self.output_dir.get()).expanduser(); output_dir.mkdir(parents=True, exist_ok=True)
        intros, default = self._intro_map()
        log_handle = self.session_log_path.open("a", encoding="utf-8", buffering=1) if self.session_log_path else None
        def raw(value: str) -> None:
            if log_handle: log_handle.write(value + "\n")
            self.events.put(("raw_log", value))
        self.engine = FFmpegLoopEngine(ffmpeg, ffprobe, lambda value: self.events.put(("log", value)), self.stop_event, use_gpu, bitrate, raw_log=raw)
        completed = failed = 0
        try:
            with tempfile.TemporaryDirectory(prefix="audio_full_") as name:
                temp = Path(name); cycle = temp / "illustration_cycle.mp4"
                self.events.put(("readable", f"Bắt đầu batch: {len(self.audio_files)} audio, {len(self.video_files)} video minh họa"))
                self.events.put(("status", "Đang tạo chu kỳ video minh họa"))
                self.engine.set_progress_callback(lambda value: self.events.put(("stage_progress", value)))
                (self.engine.make_single_cycle(self.video_files[0], cycle, fade) if len(self.video_files) == 1 else self.engine.make_multi_cycle(self.video_files, cycle, fade))
                normalized: dict[Path, tuple[Path, float]] = {}
                for index, audio in enumerate(self.audio_files, 1):
                    if self.stop_event.is_set(): raise InterruptedError("Đã dừng theo yêu cầu.")
                    self.events.put(("item_start", (audio, index, completed, failed)))
                    try:
                        duration = self.engine.duration(audio); intro = self.find_intro(audio, intros, default)
                        self.events.put(("readable", f"[{index}/{len(self.audio_files)}] {audio.name} | Intro: {intro.name if intro else 'Không có intro'}"))
                        parts: list[Path] = []; intro_duration = 0.0
                        if intro:
                            self.events.put(("item_stage", (audio, "Chuẩn hóa intro")))
                            if intro not in normalized:
                                target = temp / f"intro_{len(normalized)}.mp4"; self.engine.set_progress_callback(lambda value, a=audio: self.events.put(("item_progress", (a, value * .15))))
                                normalized[intro] = (target, self.engine.normalize_intro(intro, target, self.engine.duration(intro)))
                            intro_file, intro_duration = normalized[intro]; intro_duration = min(intro_duration, duration); parts.append(intro_file)
                        remaining = max(0.0, duration - intro_duration)
                        if remaining > .02:
                            self.events.put(("item_stage", (audio, "Loop video minh họa"))); loop_part = temp / f"loop_{index}.mp4"
                            self.engine.set_progress_callback(lambda value, a=audio: self.events.put(("item_progress", (a, 15 + value * .55))))
                            self.engine.repeat_cycle(cycle, loop_part, remaining); parts.append(loop_part)
                        visual = parts[0] if len(parts) == 1 else temp / f"visual_{index}.mp4"
                        if len(parts) > 1:
                            self.events.put(("item_stage", (audio, "Ghép intro và video"))); self.engine.concat_video_parts(parts, visual)
                        channel = output_dir / audio.parent.name; channel.mkdir(parents=True, exist_ok=True); output = channel / f"{audio.stem}_FULL.mp4"
                        self.events.put(("item_stage", (audio, "Ghép lời thoại"))); self.engine.set_progress_callback(lambda value, a=audio: self.events.put(("item_progress", (a, 70 + value * .30))))
                        self.engine.mux_narration(visual, audio, output, duration); completed += 1
                        self.events.put(("item_done", (audio, completed, failed, output)))
                        if remaining > .02: loop_part.unlink(missing_ok=True)
                        if visual.parent == temp and visual.name.startswith("visual_"): visual.unlink(missing_ok=True)
                    except InterruptedError: raise
                    except Exception as error:
                        failed += 1; self.events.put(("item_failed", (audio, completed, failed, str(error))))
                self.events.put(("readable", f"Kết thúc batch: hoàn tất {completed}, thất bại {failed}"))
            self.events.put(("done", str(output_dir)))
        except InterruptedError as error: self.events.put(("stopped", str(error)))
        except Exception as error: self.events.put(("error", str(error)))
        finally:
            if log_handle: log_handle.close()

    def _append_raw(self, value: str) -> None:
        self.raw_log.configure(state="normal"); self.raw_log.insert("end", value + "\n")
        lines = int(self.raw_log.index("end-1c").split(".")[0])
        if lines > self.LOG_LINE_LIMIT: self.raw_log.delete("1.0", f"{lines - self.LOG_LINE_LIMIT}.0")
        self.raw_log.see("end"); self.raw_log.configure(state="disabled")

    def _poll_events(self) -> None:
        try:
            for _ in range(250):
                kind, value = self.events.get_nowait()
                if kind == "preview":
                    audio, duration, intro = value; self.preview_data[audio] = (duration, intro); self._set_row(audio, duration=duration, intro=intro)
                elif kind in {"log", "readable"}: self._append_log(value)
                elif kind == "raw_log": self._append_raw(str(value))
                elif kind == "status": self.status.set(str(value)); self.app.update_tab_status(self)
                elif kind == "item_start":
                    audio, _index, completed, failed = value; self.active_audio = audio; self.current_progress.set(0); self._set_row(audio, status="Đang xử lý", percent=0); self._update_counts(completed, failed)
                elif kind == "item_stage":
                    audio, stage = value; self._set_row(audio, status=stage)
                elif kind == "item_progress":
                    audio, percent = value; percent = max(0.0, min(100.0, float(percent))); self.current_progress.set(percent); self.current_progress_text.set(f"File hiện tại: {percent:.1f}% · {audio.name}"); self._set_row(audio, percent=percent)
                    whole = batch_percent(self.completed_count.get(), self.failed_count.get(), percent, len(self.audio_files)); self.batch_progress.set(whole); self.batch_progress_text.set(f"Toàn batch: {whole:.1f}%")
                elif kind == "item_done":
                    audio, completed, failed, output = value; self._set_row(audio, status="Hoàn tất", percent=100); self._append_log(f"HOÀN TẤT: {output}"); self.active_audio = None; self._update_counts(completed, failed); self.batch_progress.set(batch_percent(completed, failed, 0, len(self.audio_files)))
                elif kind == "item_failed":
                    audio, completed, failed, error = value; self._set_row(audio, status="Thất bại"); self._append_log(f"THẤT BẠI: {audio.name} | {error}"); self.active_audio = None; self._update_counts(completed, failed); self.batch_progress.set(batch_percent(completed, failed, 0, len(self.audio_files)))
                elif kind == "done": self._finish("Hoàn tất"); self.batch_progress.set(100); self.batch_progress_text.set("Toàn batch: 100%"); messagebox.showinfo("Hoàn tất", f"Đã lưu kết quả tại:\n{value}")
                elif kind == "stopped": self._finish("Đã dừng")
                elif kind == "error": self._finish("Có lỗi"); messagebox.showerror("Lỗi xử lý", str(value))
                elif kind == "stage_progress": pass
        except queue.Empty: pass
        self.after(120, self._poll_events)


class LoopVideoSuiteApp(ttk.Window):
    def __init__(self) -> None:
        super().__init__(title="Loop Video Suite", themename="litera", size=(1480, 900), minsize=(1100, 720), high_dpi=True)
        self.option_add("*Font", "{Segoe UI} 10")
        self.store = SettingsStore(); self.theme_name = self.store.load_theme(); self.active_tab: ProcessingTab | None = None
        for definition in (mint_theme("mint-light", LIGHT, "light"), mint_theme("mint-dark", DARK, "dark")):
            if definition.name not in self.style.theme_names():
                self.style.register_theme(definition)
        self._build(); self.apply_theme(); self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        self.header = ttk.Frame(self, style="Header.TFrame", padding=(24, 15)); self.header.pack(fill="x")
        mark = tk.Canvas(self.header, width=48, height=48, highlightthickness=0, bd=0)
        mark.pack(side="left")
        self.mark_canvas = mark
        title = ttk.Frame(self.header, style="Header.TFrame"); title.pack(side="left", padx=(12, 0))
        ttk.Label(title, text="LOOP VIDEO SUITE", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title, text="Mint Workspace · Batch video production", style="Subtitle.TLabel").pack(anchor="w")
        self.ffmpeg_status = tk.StringVar(value="FFmpeg đang kiểm tra...")
        ttk.Label(self.header, textvariable=self.ffmpeg_status, style="HeaderStatus.TLabel").pack(side="right", padx=(14, 0))
        self.theme_button = ttk.Button(self.header, command=self.toggle_theme, bootstyle="secondary-outline"); self.theme_button.pack(side="right", ipady=5)
        ffmpeg, ffprobe = find_ffmpeg_tools(); self.ffmpeg_status.set("FFmpeg + GPU: Sẵn sàng" if ffmpeg and ffprobe else "FFmpeg: Chưa tìm thấy")
        self.notebook = ttk.Notebook(self, style="Mint.TNotebook"); self.notebook.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.loop_tab = LoopTab(self.notebook, self); self.audio_tab = EnhancedAudioTab(self.notebook, self)
        self.notebook.add(self.loop_tab, text="  LOOP VIDEO  "); self.notebook.add(self.audio_tab, text="  AUDIO + VIDEO + INTRO  ")

    def apply_theme(self) -> None:
        c = LIGHT if self.theme_name == "light" else DARK; self.configure(bg=c["bg"])
        s = self.style
        s.theme_use("mint-light" if self.theme_name == "light" else "mint-dark")
        s.configure(".", background=c["bg"], foreground=c["text"], fieldbackground=c["field"], bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"], focuscolor=c["accent"])
        s.configure("App.TFrame", background=c["bg"]); s.configure("Header.TFrame", background=c["surface"]); s.configure("Panel.TFrame", background=c["surface"], relief="flat")
        s.configure("TLabel", background=c["bg"], foreground=c["text"]); s.configure("Panel.TLabel", background=c["surface"], foreground=c["text"])
        s.configure("Title.TLabel", background=c["surface"], foreground=c["text"], font=("Segoe UI Semibold", 20)); s.configure("Subtitle.TLabel", background=c["surface"], foreground=c["muted"])
        s.configure("HeaderStatus.TLabel", background=c["surface"], foreground=c["success"])
        s.configure("Section.TLabel", background=c["surface"], foreground=c["muted"], font=("Segoe UI", 11, "bold")); s.configure("Heading.TLabel", background=c["surface"], foreground=c["text"], font=("Segoe UI", 16, "bold"))
        s.configure("Status.TLabel", background=c["surface"], foreground=c["success"]); s.configure("Help.TLabel", background=c["surface"], foreground=c["muted"])
        s.configure("Estimate.TLabel", background=c["surface"], foreground=c["accent"], bordercolor=c["accent"], relief="solid", padding=8)
        s.configure("TButton", background=c["field"], foreground=c["text"], borderwidth=0, padding=(13, 8)); s.map("TButton", background=[("active", c["border"]), ("disabled", c["field"])], foreground=[("disabled", c["muted"])])
        s.configure("Primary.TButton", background=c["accent"], foreground=c["accent_text"], font=("Segoe UI", 10, "bold")); s.map("Primary.TButton", background=[("active", c["success"]), ("disabled", c["field"])], foreground=[("disabled", c["muted"])])
        s.configure("TEntry", fieldbackground=c["field"], foreground=c["text"], insertcolor=c["text"], padding=8); s.configure("TSpinbox", fieldbackground=c["field"], foreground=c["text"], arrowsize=16); s.configure("TCombobox", fieldbackground=c["field"], foreground=c["text"], padding=8)
        s.configure("TCheckbutton", background=c["surface"], foreground=c["text"], padding=5); s.map("TCheckbutton", background=[("active", c["surface"])])
        s.configure("Mint.TNotebook", background=c["bg"], borderwidth=0, tabmargins=(0, 10, 0, 0)); s.configure("Mint.TNotebook.Tab", background=c["bg"], foreground=c["muted"], padding=(24, 13), font=("Segoe UI", 10, "bold"))
        s.map("Mint.TNotebook.Tab", background=[("selected", c["accent"])], foreground=[("selected", c["accent_text"]), ("active", c["text"])])
        s.configure("Horizontal.TProgressbar", background=c["accent"], troughcolor=c["field"], borderwidth=0)
        self.theme_button.configure(text="LIGHT MODE" if self.theme_name == "light" else "DARK MODE")
        self.mark_canvas.configure(bg=c["surface"])
        self.mark_canvas.delete("all")
        self.mark_canvas.create_rectangle(0, 0, 48, 48, fill=c["accent"], outline=c["accent"])
        self.mark_canvas.create_polygon(18, 13, 18, 35, 35, 24, fill=c["accent_text"], outline=c["accent_text"])
        self.loop_tab.apply_native_theme(c); self.audio_tab.apply_native_theme(c)

    def toggle_theme(self) -> None:
        self.theme_name = "dark" if self.theme_name == "light" else "light"; self.store.save_theme(self.theme_name); self.apply_theme()

    def acquire_job(self, owner: ProcessingTab) -> bool:
        if self.active_tab and self.active_tab is not owner:
            messagebox.showwarning("Đang có tác vụ", "Hãy hoàn tất hoặc dừng tác vụ ở tab còn lại trước."); return False
        self.active_tab = owner; return True

    def release_job(self, owner: ProcessingTab) -> None:
        if self.active_tab is owner: self.active_tab = None
        self.update_tab_status(owner)

    def update_tab_status(self, owner: ProcessingTab) -> None:
        index = 0 if owner is self.loop_tab else 1; base = "LOOP VIDEO" if index == 0 else "AUDIO + VIDEO + INTRO"
        suffix = "  [ĐANG CHẠY]" if owner.is_running() else ""; self.notebook.tab(index, text=f"  {base}{suffix}  ")

    def _close(self) -> None:
        if self.active_tab and self.active_tab.is_running():
            if not messagebox.askyesno("Đang xử lý", "Dừng tác vụ và đóng ứng dụng?"): return
            self.active_tab.stop()
        self.destroy()


def main() -> None:
    LoopVideoSuiteApp().mainloop()


if __name__ == "__main__":
    main()
