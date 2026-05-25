"""
╔══════════════════════════════════════╗
║       SONIC MP3 PLAYER               ║
║       Windows Desktop App            ║
║  Requires: pip install pygame mutagen║
╚══════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import threading
import time
import random

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


# ─── COLORS & FONTS ───────────────────────────────────────────────────────────
BG        = "#0D0D0D"
SURFACE   = "#161616"
CARD      = "#1E1E1E"
ACCENT    = "#FF4D4D"
ACCENT2   = "#FF8C42"
TEXT      = "#F0F0F0"
SUBTEXT   = "#888888"
HIGHLIGHT = "#2A2A2A"
BORDER    = "#2E2E2E"

FONT_TITLE  = ("Courier New", 22, "bold")
FONT_SONG   = ("Courier New", 13, "bold")
FONT_META   = ("Courier New", 10)
FONT_SMALL  = ("Courier New", 9)
FONT_BTN    = ("Courier New", 16, "bold")
FONT_TIME   = ("Courier New", 11)


class MP3Player:
    def __init__(self, root):
        self.root = root
        self.root.title("SONIC — MP3 Player")
        self.root.geometry("520x720")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        # State
        self.playlist       = []
        self.current_index  = -1
        self.is_playing     = False
        self.is_paused      = False
        self.shuffle_on     = False
        self.repeat_on      = False
        self.volume         = 0.7
        self.duration       = 0
        self.seeking        = False
        self._update_job    = None

        # Init audio
        self.audio_ok = False
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
                pygame.mixer.music.set_endevent(pygame.USEREVENT)
                self.audio_ok = True
            except Exception:
                pass

        self._build_ui()
        self._check_pygame_events()

    # ── UI BUILD ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=BG, pady=18)
        hdr.pack(fill="x")
        tk.Label(hdr, text="◈ SONIC", font=FONT_TITLE,
                 fg=ACCENT, bg=BG).pack()
        tk.Label(hdr, text="MP3 PLAYER", font=("Courier New", 9),
                 fg=SUBTEXT, bg=BG, letter_spacing=4).pack()

        # Album art placeholder
        art_frame = tk.Frame(self.root, bg=CARD, width=200, height=200,
                             highlightthickness=2, highlightbackground=BORDER)
        art_frame.pack(pady=(0, 18))
        art_frame.pack_propagate(False)
        self.art_label = tk.Label(art_frame, text="♪", font=("Courier New", 72),
                                  fg=ACCENT, bg=CARD)
        self.art_label.place(relx=0.5, rely=0.5, anchor="center")

        # Song info
        info_frame = tk.Frame(self.root, bg=BG)
        info_frame.pack(fill="x", padx=30)

        self.title_var = tk.StringVar(value="No Track Loaded")
        self.artist_var = tk.StringVar(value="—")

        tk.Label(info_frame, textvariable=self.title_var,
                 font=FONT_SONG, fg=TEXT, bg=BG,
                 wraplength=440, justify="center").pack()
        tk.Label(info_frame, textvariable=self.artist_var,
                 font=FONT_META, fg=SUBTEXT, bg=BG).pack(pady=(2, 0))

        # Progress bar
        prog_frame = tk.Frame(self.root, bg=BG)
        prog_frame.pack(fill="x", padx=30, pady=(18, 4))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = tk.Scale(
            prog_frame, from_=0, to=100, orient="horizontal",
            variable=self.progress_var,
            bg=BG, fg=ACCENT, troughcolor=SURFACE,
            activebackground=ACCENT2, highlightthickness=0,
            sliderlength=14, sliderrelief="flat", length=460,
            showvalue=False, command=self._on_seek_move
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.bind("<ButtonPress-1>",   self._seek_start)
        self.progress_bar.bind("<ButtonRelease-1>", self._seek_end)

        time_row = tk.Frame(self.root, bg=BG)
        time_row.pack(fill="x", padx=30)
        self.time_cur  = tk.Label(time_row, text="0:00", font=FONT_TIME,
                                  fg=SUBTEXT, bg=BG)
        self.time_cur.pack(side="left")
        self.time_total = tk.Label(time_row, text="0:00", font=FONT_TIME,
                                   fg=SUBTEXT, bg=BG)
        self.time_total.pack(side="right")

        # Volume
        vol_frame = tk.Frame(self.root, bg=BG)
        vol_frame.pack(fill="x", padx=30, pady=(6, 0))
        tk.Label(vol_frame, text="VOL", font=FONT_SMALL,
                 fg=SUBTEXT, bg=BG).pack(side="left")
        self.vol_var = tk.DoubleVar(value=self.volume * 100)
        vol_slider = tk.Scale(
            vol_frame, from_=0, to=100, orient="horizontal",
            variable=self.vol_var,
            bg=BG, fg=ACCENT2, troughcolor=SURFACE,
            activebackground=ACCENT, highlightthickness=0,
            sliderlength=12, sliderrelief="flat", length=390,
            showvalue=False, command=self._on_volume
        )
        vol_slider.pack(side="left", padx=(6, 0), fill="x", expand=True)

        # Control buttons
        ctrl = tk.Frame(self.root, bg=BG)
        ctrl.pack(pady=20)

        btn_cfg = dict(bg=CARD, fg=TEXT, activebackground=HIGHLIGHT,
                       activeforeground=ACCENT, relief="flat",
                       font=FONT_BTN, bd=0, padx=14, pady=8,
                       cursor="hand2")

        self.shuf_btn = tk.Button(ctrl, text="⇄", command=self._toggle_shuffle,
                                  **btn_cfg)
        self.shuf_btn.grid(row=0, column=0, padx=6)

        tk.Button(ctrl, text="⏮", command=self._prev_track,
                  **btn_cfg).grid(row=0, column=1, padx=6)

        self.play_btn = tk.Button(ctrl, text="▶", command=self._play_pause,
                                  bg=ACCENT, fg=TEXT,
                                  activebackground=ACCENT2, activeforeground=TEXT,
                                  relief="flat", font=("Courier New", 18, "bold"),
                                  bd=0, padx=18, pady=8, cursor="hand2")
        self.play_btn.grid(row=0, column=2, padx=10)

        tk.Button(ctrl, text="⏭", command=self._next_track,
                  **btn_cfg).grid(row=0, column=3, padx=6)

        self.rep_btn = tk.Button(ctrl, text="↺", command=self._toggle_repeat,
                                 **btn_cfg)
        self.rep_btn.grid(row=0, column=4, padx=6)

        # Playlist panel
        pl_wrap = tk.Frame(self.root, bg=SURFACE,
                           highlightthickness=1, highlightbackground=BORDER)
        pl_wrap.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        pl_header = tk.Frame(pl_wrap, bg=SURFACE)
        pl_header.pack(fill="x", padx=10, pady=8)
        tk.Label(pl_header, text="PLAYLIST", font=("Courier New", 10, "bold"),
                 fg=ACCENT, bg=SURFACE).pack(side="left")

        btn_row = tk.Frame(pl_header, bg=SURFACE)
        btn_row.pack(side="right")
        for txt, cmd in [("+ ADD", self._add_files),
                         ("📁 FOLDER", self._add_folder),
                         ("✕ CLEAR", self._clear_playlist)]:
            tk.Button(btn_row, text=txt, command=cmd,
                      bg=HIGHLIGHT, fg=TEXT, relief="flat",
                      font=FONT_SMALL, padx=6, pady=2,
                      activebackground=ACCENT, activeforeground=TEXT,
                      cursor="hand2").pack(side="left", padx=2)

        list_frame = tk.Frame(pl_wrap, bg=SURFACE)
        list_frame.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        scrollbar = tk.Scrollbar(list_frame, bg=SURFACE,
                                 troughcolor=SURFACE, relief="flat")
        scrollbar.pack(side="right", fill="y")

        self.playlist_box = tk.Listbox(
            list_frame, bg=SURFACE, fg=TEXT,
            selectbackground=ACCENT, selectforeground=TEXT,
            font=FONT_SMALL, relief="flat", bd=0,
            highlightthickness=0, activestyle="none",
            yscrollcommand=scrollbar.set, cursor="hand2"
        )
        self.playlist_box.pack(fill="both", expand=True)
        self.playlist_box.bind("<Double-Button-1>", self._on_playlist_dclick)
        scrollbar.config(command=self.playlist_box.yview)

        # Status bar
        self.status_var = tk.StringVar(value="Ready — Add MP3 files to begin")
        tk.Label(self.root, textvariable=self.status_var,
                 font=FONT_SMALL, fg=SUBTEXT, bg=BG,
                 pady=4).pack()

        if not self.audio_ok:
            self._set_status("⚠ pygame not found — run: pip install pygame mutagen")

    # ── AUDIO CONTROLS ────────────────────────────────────────────────────────

    def _play_track(self, index):
        if not self.playlist or index < 0 or index >= len(self.playlist):
            return
        if not self.audio_ok:
            messagebox.showerror("Missing Library",
                                 "Please install pygame:\n\npip install pygame mutagen")
            return

        self.current_index = index
        path = self.playlist[index]
        name = os.path.basename(path)

        # Metadata
        title, artist = os.path.splitext(name)[0], "Unknown Artist"
        self.duration = 0
        if MUTAGEN_AVAILABLE:
            try:
                audio = MP3(path)
                self.duration = audio.info.length
                tags = ID3(path)
                t = tags.get("TIT2"); title  = str(t) if t else title
                a = tags.get("TPE1"); artist = str(a) if a else artist
            except Exception:
                pass

        self.title_var.set(title[:48] + ("…" if len(title) > 48 else ""))
        self.artist_var.set(artist)
        self.time_total.config(text=self._fmt_time(self.duration))
        self.progress_var.set(0)

        # Highlight playlist
        self.playlist_box.selection_clear(0, "end")
        self.playlist_box.selection_set(index)
        self.playlist_box.see(index)
        self._refresh_playlist_colors()

        # Play
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play()
            self.is_playing = True
            self.is_paused  = False
            self.play_btn.config(text="⏸")
            self._set_status(f"▶ Playing: {name}")
            self._start_progress()
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _play_pause(self):
        if not self.audio_ok:
            messagebox.showerror("Missing Library",
                                 "Install pygame first:\n\npip install pygame mutagen")
            return
        if not self.playlist:
            self._add_files(); return

        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True
            self.play_btn.config(text="▶")
            self._set_status("⏸ Paused")
        elif self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.play_btn.config(text="⏸")
            self._set_status("▶ Resumed")
        else:
            idx = max(self.current_index, 0)
            self._play_track(idx)

    def _next_track(self):
        if not self.playlist: return
        if self.shuffle_on:
            idx = random.randint(0, len(self.playlist) - 1)
        else:
            idx = (self.current_index + 1) % len(self.playlist)
        self._play_track(idx)

    def _prev_track(self):
        if not self.playlist: return
        pos = pygame.mixer.music.get_pos() / 1000 if self.audio_ok else 0
        if pos > 3:
            pygame.mixer.music.rewind()
        else:
            idx = (self.current_index - 1) % len(self.playlist)
            self._play_track(idx)

    def _on_volume(self, val):
        self.volume = float(val) / 100
        if self.audio_ok:
            pygame.mixer.music.set_volume(self.volume)

    def _toggle_shuffle(self):
        self.shuffle_on = not self.shuffle_on
        self.shuf_btn.config(fg=ACCENT if self.shuffle_on else TEXT)
        self._set_status("Shuffle ON" if self.shuffle_on else "Shuffle OFF")

    def _toggle_repeat(self):
        self.repeat_on = not self.repeat_on
        self.rep_btn.config(fg=ACCENT if self.repeat_on else TEXT)
        self._set_status("Repeat ON" if self.repeat_on else "Repeat OFF")

    # ── SEEK ──────────────────────────────────────────────────────────────────

    def _seek_start(self, event):
        self.seeking = True

    def _on_seek_move(self, val):
        if self.seeking and self.duration > 0:
            secs = float(val) / 100 * self.duration
            self.time_cur.config(text=self._fmt_time(secs))

    def _seek_end(self, event):
        if self.seeking and self.duration > 0 and self.audio_ok and self.is_playing:
            pos = self.progress_var.get() / 100 * self.duration
            pygame.mixer.music.set_pos(pos)
        self.seeking = False

    # ── PROGRESS ──────────────────────────────────────────────────────────────

    def _start_progress(self):
        if self._update_job:
            self.root.after_cancel(self._update_job)
        self._update_progress()

    def _update_progress(self):
        if self.is_playing and not self.is_paused and not self.seeking:
            if self.audio_ok:
                ms = pygame.mixer.music.get_pos()
                if ms >= 0 and self.duration > 0:
                    secs = ms / 1000
                    pct  = min(secs / self.duration * 100, 100)
                    self.progress_var.set(pct)
                    self.time_cur.config(text=self._fmt_time(secs))
        self._update_job = self.root.after(500, self._update_progress)

    # ── PLAYLIST MANAGEMENT ───────────────────────────────────────────────────

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="Select MP3 Files",
            filetypes=[("MP3 Files", "*.mp3"), ("All Files", "*.*")]
        )
        for f in files:
            if f not in self.playlist:
                self.playlist.append(f)
                self.playlist_box.insert("end", "  " + os.path.basename(f))
        if files:
            self._set_status(f"Added {len(files)} file(s)")
            if self.current_index < 0:
                self.current_index = 0

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select Music Folder")
        if folder:
            count = 0
            for fn in sorted(os.listdir(folder)):
                if fn.lower().endswith(".mp3"):
                    fp = os.path.join(folder, fn)
                    if fp not in self.playlist:
                        self.playlist.append(fp)
                        self.playlist_box.insert("end", "  " + fn)
                        count += 1
            self._set_status(f"Added {count} MP3(s) from folder")
            if count and self.current_index < 0:
                self.current_index = 0

    def _clear_playlist(self):
        if messagebox.askyesno("Clear Playlist", "Remove all tracks?"):
            if self.audio_ok:
                pygame.mixer.music.stop()
            self.playlist.clear()
            self.playlist_box.delete(0, "end")
            self.current_index = -1
            self.is_playing = self.is_paused = False
            self.play_btn.config(text="▶")
            self.title_var.set("No Track Loaded")
            self.artist_var.set("—")
            self.progress_var.set(0)
            self.time_cur.config(text="0:00")
            self.time_total.config(text="0:00")
            self._set_status("Playlist cleared")

    def _on_playlist_dclick(self, event):
        sel = self.playlist_box.curselection()
        if sel:
            self._play_track(sel[0])

    def _refresh_playlist_colors(self):
        for i in range(self.playlist_box.size()):
            self.playlist_box.itemconfig(
                i,
                fg=ACCENT if i == self.current_index else TEXT,
                bg=HIGHLIGHT if i == self.current_index else SURFACE
            )

    # ── PYGAME EVENT LOOP ─────────────────────────────────────────────────────

    def _check_pygame_events(self):
        if self.audio_ok:
            try:
                for event in pygame.event.get():
                    if event.type == pygame.USEREVENT:
                        if self.repeat_on:
                            self._play_track(self.current_index)
                        else:
                            self._next_track()
            except Exception:
                pass
        self.root.after(300, self._check_pygame_events)

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _set_status(self, msg):
        self.status_var.set(msg)

    @staticmethod
    def _fmt_time(secs):
        secs = int(secs)
        return f"{secs // 60}:{secs % 60:02d}"


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not PYGAME_AVAILABLE:
        import tkinter.messagebox as mb
        root_tmp = tk.Tk(); root_tmp.withdraw()
        mb.showerror(
            "Missing Dependencies",
            "Please install required libraries first:\n\n"
            "  pip install pygame mutagen\n\n"
            "Then run this script again."
        )
        root_tmp.destroy()
    else:
        root = tk.Tk()
        app  = MP3Player(root)
        root.mainloop()
