from __future__ import annotations

import queue
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from video_loop_tool import FFmpegLoopEngine, VIDEO_EXTENSIONS, find_ffmpeg_tools


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


class AudioFullApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Audio + Video Minh Hoa - Batch FULL")
        self.geometry("1120x780")
        self.minsize(900, 680)
        self.configure(bg="#101914")
        self.option_add("*Font", "{Segoe UI} 10")
        self.audio_files: list[Path] = []
        self.video_files: list[Path] = []
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
        style.configure("Title.TLabel", font=("Georgia", 21, "bold"), foreground="#f4c95d")
        style.configure("Accent.TButton", background="#f4c95d", foreground="#101914", font=("Segoe UI", 10, "bold"))

    def _build(self) -> None:
        header = ttk.Frame(self, padding=(20, 15))
        header.pack(fill="x")
        ttk.Label(header, text="AUDIO + VIDEO MINH HOA", style="Title.TLabel").pack(side="left")
        self.status = tk.StringVar(value="San sang")
        ttk.Label(header, textvariable=self.status).pack(side="right")

        body = ttk.Frame(self, padding=(18, 0, 18, 18))
        body.pack(fill="both", expand=True)
        settings = ttk.Frame(body, style="Card.TFrame", padding=14)
        settings.pack(side="left", fill="y", padx=(0, 12))
        content = ttk.Frame(body)
        content.pack(side="left", fill="both", expand=True)

        self.video_dir = tk.StringVar()
        self.intro_dir = tk.StringVar()
        self.default_intro = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path.home() / "Videos" / "Full"))
        self.fade = tk.DoubleVar(value=0.7)
        self.bitrate = tk.DoubleVar(value=10.0)
        self.use_gpu = tk.BooleanVar(value=True)

        ttk.Label(settings, text="CAU HINH BATCH", style="Card.TLabel", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        self._path_field(settings, "Thu muc video minh hoa", self.video_dir, self._choose_video_dir)
        self._path_field(settings, "Thu muc intro theo kenh", self.intro_dir, self._choose_intro_dir)
        self._path_field(settings, "Intro mac dinh (tuy chon)", self.default_intro, self._choose_default_intro)
        self._path_field(settings, "Thu muc xuat", self.output_dir, self._choose_output)

        for label, variable, start, end, step in (
            ("Hoa tron video (giay)", self.fade, 0.1, 3.0, 0.1),
            ("Bitrate video (Mbps)", self.bitrate, 1.0, 100.0, 0.5),
        ):
            ttk.Label(settings, text=label, style="Card.TLabel").pack(anchor="w", pady=(11, 3))
            ttk.Spinbox(settings, from_=start, to=end, increment=step, textvariable=variable).pack(fill="x")
        ttk.Checkbutton(settings, text="Dung GPU NVIDIA NVENC", variable=self.use_gpu).pack(anchor="w", pady=(12, 2))
        ttk.Label(
            settings,
            text="Quy tac intro:\nAudio trong .../Kenh_A/file.mp3\nse dung intro Kenh_A.mp4.\nKhong tim thay -> intro mac dinh.",
            style="Card.TLabel", justify="left", foreground="#a8cdb3",
        ).pack(anchor="w", pady=(12, 4))
        self.start_button = ttk.Button(settings, text="TAO VIDEO _FULL", style="Accent.TButton", command=self._start)
        self.start_button.pack(fill="x", pady=(18, 5))
        ttk.Button(settings, text="Dung", command=self._stop).pack(fill="x")

        actions = ttk.Frame(content)
        actions.pack(fill="x")
        ttk.Button(actions, text="Them audio", command=self._add_audio).pack(side="left", padx=(0, 5))
        ttk.Button(actions, text="Nap thu muc audio", command=self._add_audio_folder).pack(side="left", padx=5)
        ttk.Button(actions, text="Xoa danh sach", command=self._clear_audio).pack(side="left", padx=5)
        self.audio_list = tk.Listbox(content, height=12, bg="#18251e", fg="#f2eadb", selectbackground="#b97435", relief="flat")
        self.audio_list.pack(fill="x", pady=10)
        self.progress = ttk.Progressbar(content, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 8))
        self.log = tk.Text(content, bg="#0b110e", fg="#b9d8c2", relief="flat", state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

    def _path_field(self, parent, label: str, variable: tk.StringVar, command) -> None:
        ttk.Label(parent, text=label, style="Card.TLabel").pack(anchor="w", pady=(10, 3))
        ttk.Entry(parent, textvariable=variable, width=35).pack(fill="x")
        ttk.Button(parent, text="Chon", command=command).pack(fill="x", pady=(3, 0))

    def _choose_video_dir(self) -> None:
        value = filedialog.askdirectory(title="Chon thu muc video minh hoa")
        if value:
            self.video_dir.set(value)

    def _choose_intro_dir(self) -> None:
        value = filedialog.askdirectory(title="Chon thu muc intro theo kenh")
        if value:
            self.intro_dir.set(value)

    def _choose_default_intro(self) -> None:
        value = filedialog.askopenfilename(title="Chon intro mac dinh", filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v")])
        if value:
            self.default_intro.set(value)

    def _choose_output(self) -> None:
        value = filedialog.askdirectory(title="Chon thu muc xuat")
        if value:
            self.output_dir.set(value)

    def _add_audio(self) -> None:
        values = filedialog.askopenfilenames(title="Chon audio", filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus")])
        self._append_audio([Path(value) for value in values])

    def _add_audio_folder(self) -> None:
        value = filedialog.askdirectory(title="Chon thu muc audio goc")
        if value:
            root = Path(value)
            self._append_audio(sorted(path for path in root.rglob("*") if path.suffix.lower() in AUDIO_EXTENSIONS))

    def _append_audio(self, paths: list[Path]) -> None:
        known = {path.resolve() for path in self.audio_files}
        for path in paths:
            if path.resolve() not in known:
                self.audio_files.append(path)
                known.add(path.resolve())
                self.audio_list.insert("end", str(path))
        self.status.set(f"Da chon {len(self.audio_files)} audio")

    def _clear_audio(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.audio_files.clear()
        self.audio_list.delete(0, "end")

    def _find_intro(self, audio: Path, intros: dict[str, Path], default: Path | None) -> Path | None:
        channel = audio.parent.name.casefold()
        if channel in intros:
            return intros[channel]
        stem = audio.stem.casefold()
        matches = [(name, path) for name, path in intros.items() if stem.startswith(name)]
        if matches:
            return max(matches, key=lambda item: len(item[0]))[1]
        return default

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        video_dir = Path(self.video_dir.get())
        if not self.audio_files:
            messagebox.showwarning("Thieu audio", "Hay them it nhat mot file audio.")
            return
        if not video_dir.is_dir():
            messagebox.showwarning("Thieu video", "Hay chon thu muc video minh hoa.")
            return
        videos = sorted(path for path in video_dir.iterdir() if path.suffix.lower() in VIDEO_EXTENSIONS)
        if not videos:
            messagebox.showwarning("Thieu video", "Thu muc khong co video minh hoa hop le.")
            return
        ffmpeg, ffprobe = find_ffmpeg_tools()
        if not ffmpeg or not ffprobe:
            messagebox.showerror("Thieu FFmpeg", "Khong tim thay FFmpeg/ffprobe.")
            return
        self.video_files = videos
        self.stop_event.clear()
        self.progress.configure(maximum=len(self.audio_files), value=0)
        self.start_button.configure(state="disabled")
        settings = (self.fade.get(), self.bitrate.get(), self.use_gpu.get())
        self.worker = threading.Thread(target=self._work, args=(ffmpeg, ffprobe, settings), daemon=True)
        self.worker.start()

    def _work(self, ffmpeg: str, ffprobe: str, settings: tuple[float, float, bool]) -> None:
        fade, bitrate, use_gpu = settings
        output_dir = Path(self.output_dir.get()).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        intro_root = Path(self.intro_dir.get()) if self.intro_dir.get() else None
        intros = {
            path.stem.casefold(): path for path in (intro_root.iterdir() if intro_root and intro_root.is_dir() else [])
            if path.suffix.lower() in VIDEO_EXTENSIONS
        }
        default_intro = Path(self.default_intro.get()) if self.default_intro.get() else None
        if default_intro and not default_intro.is_file():
            default_intro = None
        self.engine = FFmpegLoopEngine(
            ffmpeg, ffprobe, lambda value: self.events.put(("log", value)),
            self.stop_event, use_gpu=use_gpu, bitrate_mbps=bitrate,
        )
        try:
            with tempfile.TemporaryDirectory(prefix="audio_full_") as temp_name:
                temp = Path(temp_name)
                cycle = temp / "illustration_cycle.mp4"
                self.events.put(("status", f"Dang tao chu ky tu {len(self.video_files)} video..."))
                if len(self.video_files) == 1:
                    self.engine.make_single_cycle(self.video_files[0], cycle, fade)
                else:
                    self.engine.make_multi_cycle(self.video_files, cycle, fade)

                normalized_intros: dict[Path, tuple[Path, float]] = {}
                for index, audio in enumerate(self.audio_files, 1):
                    audio_duration = self.engine.duration(audio)
                    if audio_duration <= 0.1:
                        raise ValueError(f"Audio qua ngan: {audio.name}")
                    intro = self._find_intro(audio, intros, default_intro)
                    self.events.put(("status", f"{index}/{len(self.audio_files)}: {audio.name}"))
                    parts: list[Path] = []
                    intro_duration = 0.0
                    if intro:
                        if intro not in normalized_intros:
                            normalized = temp / f"intro_{len(normalized_intros)}.mp4"
                            duration = self.engine.normalize_intro(intro, normalized, self.engine.duration(intro))
                            normalized_intros[intro] = (normalized, duration)
                        normalized, intro_duration = normalized_intros[intro]
                        intro_duration = min(intro_duration, audio_duration)
                        parts.append(normalized)
                        self.events.put(("log", f"Intro: {intro.name}"))
                    remaining = max(0.0, audio_duration - intro_duration)
                    if remaining > 0.02:
                        loop_part = temp / f"loop_{index}.mp4"
                        self.engine.repeat_cycle(cycle, loop_part, remaining)
                        parts.append(loop_part)
                    visual = temp / f"visual_{index}.mp4"
                    if len(parts) == 1:
                        visual = parts[0]
                    else:
                        self.engine.concat_video_parts(parts, visual)
                    channel_output = output_dir / audio.parent.name
                    channel_output.mkdir(parents=True, exist_ok=True)
                    output = channel_output / f"{audio.stem}_FULL.mp4"
                    self.engine.mux_narration(visual, audio, output, audio_duration)
                    self.events.put(("progress", index))
                    self.events.put(("log", f"HOAN TAT: {output}"))
                    if remaining > 0.02:
                        loop_part.unlink(missing_ok=True)
                    if visual.parent == temp and visual.name.startswith("visual_"):
                        visual.unlink(missing_ok=True)
            self.events.put(("done", str(output_dir)))
        except InterruptedError as error:
            self.events.put(("stopped", str(error)))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _stop(self) -> None:
        if self.engine:
            self.engine.stop()
        self.status.set("Dang dung...")

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
                    self.status.set("Hoan tat")
                    self.start_button.configure(state="normal")
                    messagebox.showinfo("Hoan tat", f"Da luu cac file _FULL tai:\n{value}")
                elif kind == "stopped":
                    self.status.set("Da dung")
                    self.start_button.configure(state="normal")
                elif kind == "error":
                    self.status.set("Co loi")
                    self.start_button.configure(state="normal")
                    messagebox.showerror("Loi xu ly", str(value))
        except queue.Empty:
            pass
        self.after(150, self._poll)


if __name__ == "__main__":
    AudioFullApp().mainloop()
