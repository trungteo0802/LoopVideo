from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk


def launch_tool(name: str, root: tk.Tk | None = None) -> None:
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--tool", name]
    else:
        command = [sys.executable, str(Path(__file__).resolve()), "--tool", name]
    subprocess.Popen(command)
    if root is not None:
        root.destroy()


class SuiteLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Loop Video Suite")
        self.geometry("820x510")
        self.resizable(False, False)
        self.configure(bg="#0d1712")
        self.option_add("*Font", "{Segoe UI} 10")
        self._style()
        self._build()

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#0d1712")
        style.configure("Card.TFrame", background="#18251e")
        style.configure("TLabel", background="#0d1712", foreground="#f2eadb")
        style.configure("Card.TLabel", background="#18251e", foreground="#f2eadb")
        style.configure("Title.TLabel", font=("Georgia", 25, "bold"), foreground="#f4c95d")
        style.configure("Tool.TButton", background="#f4c95d", foreground="#101914", font=("Segoe UI", 11, "bold"), padding=(14, 11))
        style.map("Tool.TButton", background=[("active", "#ffe08a")])

    def _build(self) -> None:
        header = ttk.Frame(self, padding=(30, 28, 30, 18))
        header.pack(fill="x")
        ttk.Label(header, text="LOOP VIDEO SUITE", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Chon quy trinh can xu ly", foreground="#a8cdb3").pack(anchor="w", pady=(5, 0))

        cards = ttk.Frame(self, padding=(30, 10, 30, 30))
        cards.pack(fill="both", expand=True)
        loop_card = ttk.Frame(cards, style="Card.TFrame", padding=22)
        full_card = ttk.Frame(cards, style="Card.TFrame", padding=22)
        loop_card.pack(side="left", fill="both", expand=True, padx=(0, 9))
        full_card.pack(side="left", fill="both", expand=True, padx=(9, 0))

        ttk.Label(loop_card, text="LOOP VIDEO", style="Card.TLabel", font=("Georgia", 17, "bold"), foreground="#f4c95d").pack(anchor="w")
        ttk.Label(
            loop_card,
            text="Giu nguyen cac chuc nang cu:\n\n- 1 video -> 1 video dai\n- Nhieu video -> 1 video dai\n- Nhap gio/phut\n- Crossfade tranh giat\n- GPU NVENC va bitrate\n- Batch khong gioi han",
            style="Card.TLabel", justify="left",
        ).pack(anchor="w", fill="x", pady=(12, 18))
        ttk.Button(loop_card, text="MO TOOL LOOP CU", style="Tool.TButton", command=lambda: launch_tool("loop", self)).pack(fill="x", side="bottom")

        ttk.Label(full_card, text="AUDIO + VIDEO FULL", style="Card.TLabel", font=("Georgia", 17, "bold"), foreground="#f4c95d").pack(anchor="w")
        ttk.Label(
            full_card,
            text="Chuc nang moi rieng biet:\n\n- Do thoi luong audio\n- Intro rieng tung kenh\n- Loop video minh hoa\n- Ghep loi thoai AAC\n- Xuat hau to _FULL.mp4\n- Xu ly batch so luong lon",
            style="Card.TLabel", justify="left",
        ).pack(anchor="w", fill="x", pady=(12, 18))
        ttk.Button(full_card, text="MO AUDIO + VIDEO", style="Tool.TButton", command=lambda: launch_tool("full", self)).pack(fill="x", side="bottom")


def main() -> None:
    tool = None
    if "--tool" in sys.argv:
        index = sys.argv.index("--tool")
        if index + 1 < len(sys.argv):
            tool = sys.argv[index + 1]
    if tool == "loop":
        from video_loop_tool import VideoLoopApp
        VideoLoopApp().mainloop()
    elif tool == "full":
        from audio_full_tool import AudioFullApp
        AudioFullApp().mainloop()
    else:
        SuiteLauncher().mainloop()


if __name__ == "__main__":
    main()
