###############################################################################
# notifier.py — RefreshBrowser
# Ventana flotante de aviso 30 segundos antes del refresco.
# - Sin barra de título (discreta, siempre visible).
# - Countdown visual + barra de progreso.
# - Botones: "Cancelar refresco" y "Posponer 5 min".
# - Escape como atajo de teclado para cancelar.
# - Sonido de aviso (dos pitidos cortos).
# - Posición configurable en las cuatro esquinas de la pantalla.
###############################################################################

import threading
import tkinter as tk
from tkinter import ttk

try:
    import winsound
    _SOUND_AVAILABLE = True
except ImportError:
    _SOUND_AVAILABLE = False

CORNER_OPTIONS = [
    "Inferior derecha",
    "Inferior izquierda",
    "Superior derecha",
    "Superior izquierda",
]

# Colores del tema oscuro de la ventana flotante
_BG      = "#1e272e"
_FG      = "#dfe6e9"
_RED     = "#e74c3c"
_GRAY    = "#636e72"
_SUBTEXT = "#95a5a6"


def corner_to_coords(corner, w, h, sw, sh, mg=20, tb=48):
    """Calcula (x, y) para posicionar el aviso en una esquina de pantalla."""
    coords = {
        "Inferior derecha":   (sw - w - mg,     sh - h - mg - tb),
        "Inferior izquierda": (mg,               sh - h - mg - tb),
        "Superior derecha":   (sw - w - mg,     mg),
        "Superior izquierda": (mg,               mg),
    }
    return coords.get(corner, coords["Inferior derecha"])


class NotifierWindow:
    """
    Ventana flotante sin bordes que aparece N segundos antes del refresco.

    Parámetros
    ----------
    parent      : tk.Tk — ventana raíz (necesaria para Toplevel).
    seconds     : int   — duración del aviso en segundos.
    on_cancel   : callable — llamado cuando el usuario cancela.
    on_postpone : callable — llamado cuando el usuario pospone.
    corner      : str   — posición en pantalla (ver CORNER_OPTIONS).
    sound_enabled : bool — reproducir tono de aviso (default True).
    """

    def __init__(self, parent, seconds, on_cancel, on_postpone,
                 corner="Inferior derecha", sound_enabled=True):
        self.parent      = parent
        self.seconds_left = seconds
        self.on_cancel   = on_cancel
        self.on_postpone = on_postpone
        self.corner      = corner
        self.sound_enabled = sound_enabled
        self._active     = True

        self._build()
        self._position()
        self._tick()
        if self.sound_enabled:
            threading.Thread(target=self._beep, daemon=True).start()

    # ------------------------------------------------------------------ build
    def _build(self):
        self.win = tk.Toplevel(self.parent)
        self.win.overrideredirect(True)        # sin barra de título
        self.win.attributes("-topmost", True)  # siempre encima
        self.win.configure(bg=_BG)

        outer = tk.Frame(self.win, bg=_BG, padx=18, pady=14)
        outer.pack()

        # Título
        tk.Label(outer, text="🔄  Refresco de navegadores",
                 bg=_BG, fg=_FG,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")

        tk.Label(outer, text="El navegador se recargará automáticamente.",
                 bg=_BG, fg=_SUBTEXT,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 10))

        # Número grande de countdown
        self.count_lbl = tk.Label(outer, text=f"{self.seconds_left}s",
                                   bg=_BG, fg=_RED,
                                   font=("Segoe UI", 36, "bold"))
        self.count_lbl.pack()

        # Barra de progreso
        style = ttk.Style(self.win)
        style.theme_use("default")
        style.configure("Notifier.Horizontal.TProgressbar",
                        troughcolor=_GRAY, background=_RED, thickness=6)
        self.progress = ttk.Progressbar(
            outer, style="Notifier.Horizontal.TProgressbar",
            orient="horizontal", length=220,
            maximum=self.seconds_left, value=self.seconds_left
        )
        self.progress.pack(pady=(6, 14))

        # Botones
        btn_frame = tk.Frame(outer, bg=_BG)
        btn_frame.pack(fill="x")

        tk.Button(
            btn_frame, text="Cancelar refresco",
            command=self._cancel,
            bg=_RED, fg="white", relief="flat",
            activebackground="#c0392b", activeforeground="white",
            font=("Segoe UI", 9, "bold"), cursor="hand2",
            padx=10, pady=5
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            btn_frame, text="Posponer 5 min",
            command=self._postpone,
            bg=_GRAY, fg="white", relief="flat",
            activebackground="#4d4d4d", activeforeground="white",
            font=("Segoe UI", 9), cursor="hand2",
            padx=10, pady=5
        ).pack(side="left")

        # Atajo de teclado
        self.win.bind("<Escape>", lambda _: self._cancel())
        self.win.focus_set()

    # --------------------------------------------------------------- position
    def _position(self):
        self.win.update_idletasks()
        w  = self.win.winfo_reqwidth()
        h  = self.win.winfo_reqheight()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x, y = corner_to_coords(self.corner, w, h, sw, sh)
        self.win.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------- tick
    def _tick(self):
        if not self._active:
            return
        # Actualizar etiqueta y barra (no bajar de 0)
        display = max(0, self.seconds_left)
        self.count_lbl.config(text=f"{display}s")
        self.progress.config(value=display)

        if self.seconds_left > 0:
            self.seconds_left -= 1
            self.win.after(1000, self._tick)
        # Al llegar a 0 el worker enviará HIDE_NOTIFIER → destroy()

    # ------------------------------------------------------------------ sound
    def _beep(self):
        if not self.sound_enabled or not _SOUND_AVAILABLE:
            return
        try:
            winsound.Beep(880, 180)
            import time; time.sleep(0.12)
            winsound.Beep(880, 180)
        except Exception:
            pass

    # ---------------------------------------------------------------- actions
    def _cancel(self):
        if not self._active:
            return
        self._active = False
        self.destroy()
        if self.on_cancel:
            self.on_cancel()

    def _postpone(self):
        if not self._active:
            return
        self._active = False
        self.destroy()
        if self.on_postpone:
            self.on_postpone()

    def destroy(self):
        self._active = False
        try:
            self.win.destroy()
        except Exception:
            pass
