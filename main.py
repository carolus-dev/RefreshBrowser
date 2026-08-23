###############################################################################
# main.py — RefreshBrowser
#
# Refresca navegadores (Chrome, Edge, Firefox, Brave) en intervalos
# configurables. 30 segundos antes de cada refresco muestra una ventana
# flotante de aviso con opciones de Cancelar o Posponer 5 minutos.
#
# Dependencias:  pip install pywin32 psutil
# Compilar:      pyinstaller RefreshBrowser.spec
###############################################################################

import sys
import time
import queue
import ctypes
import threading
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# ── Expiración de licencia ────────────────────────────────────────────────────
_EXPIRY = datetime.date(2027, 8, 23)

def _check_expiry():
    if datetime.date.today() > _EXPIRY:
        _r = tk.Tk()
        _r.withdraw()
        messagebox.showerror(
            "Licencia expirada",
            f"Este programa expiró el {_EXPIRY.strftime('%d/%m/%Y')}.\n\n"
            "Contacta a CarolusDev para renovar tu licencia."
        )
        _r.destroy()
        sys.exit(0)

try:
    import win32gui        # noqa: F401  (verificación de dependencias)
    import psutil          # noqa: F401
except ImportError:
    _root = tk.Tk()
    _root.withdraw()
    messagebox.showerror(
        "Dependencias faltantes",
        "Instala las librerías necesarias:\n\n    pip install pywin32 psutil"
    )
    sys.exit(1)

from refresher import BROWSERS, refresh_browsers
from notifier  import NotifierWindow, CORNER_OPTIONS

# ── Constantes ────────────────────────────────────────────────────────────────
WARN_SECS     = 30   # segundos de aviso antes del refresco
POSTPONE_SECS = 300  # duración del posponer (5 minutos)
MIN_INTERVAL  = WARN_SECS + 1   # intervalo mínimo permitido


def _fmt(secs: float) -> str:
    """Convierte segundos a MM:SS."""
    s = max(0, int(secs))
    return f"{s // 60:02d}:{s % 60:02d}"


# ── Aplicación ────────────────────────────────────────────────────────────────
class RefreshBrowserApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RefreshBrowser")
        self.root.resizable(False, False)

        # Threading
        self.stop_event     = threading.Event()
        self.cancel_event   = threading.Event()
        self.postpone_event = threading.Event()
        self.log_queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None

        # Estado
        self.selected_processes: set[str] = set()
        self.interval_seconds: int = 100
        self.notifier: NotifierWindow | None = None

        self._build_ui()
        self._sync_selection()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(150, self._poll)

    # ── Interfaz ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=14)
        main.grid(row=0, column=0, sticky="nsew")

        # Título
        ttk.Label(main, text="RefreshBrowser",
                  font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        # ── Navegadores ──
        bf = ttk.LabelFrame(main, text="Navegadores", padding=10)
        bf.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.browser_vars: dict[str, tk.BooleanVar] = {}
        defaults = {"Google Chrome", "Microsoft Edge"}
        for i, label in enumerate(BROWSERS):
            var = tk.BooleanVar(value=(label in defaults))
            self.browser_vars[label] = var
            ttk.Checkbutton(bf, text=label, variable=var,
                            command=self._sync_selection).grid(
                row=i // 2, column=i % 2, sticky="w", padx=8, pady=3)

        # ── Intervalo ──
        ivf = ttk.LabelFrame(main, text="Intervalo de refresco", padding=10)
        ivf.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        ttk.Label(ivf, text="Cada").grid(row=0, column=0, padx=(0, 6))

        self.interval_var = tk.StringVar(value="100")
        self.interval_spin = ttk.Spinbox(
            ivf, from_=MIN_INTERVAL, to=86400,
            width=8, textvariable=self.interval_var
        )
        self.interval_spin.grid(row=0, column=1)

        self.unit_var = tk.StringVar(value="segundos")
        self.unit_combo = ttk.Combobox(
            ivf, textvariable=self.unit_var, width=10, state="readonly",
            values=["segundos", "minutos", "horas"]
        )
        self.unit_combo.grid(row=0, column=2, padx=6)

        ttk.Label(ivf,
                  text=f"Mínimo {MIN_INTERVAL}s  —  el aviso aparece {WARN_SECS}s antes",
                  foreground="#888", font=("Segoe UI", 8)).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # ── Posición del aviso ──
        pf = ttk.LabelFrame(main, text="Posición del aviso flotante", padding=10)
        pf.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.corner_var = tk.StringVar(value="Inferior derecha")
        ttk.Combobox(pf, textvariable=self.corner_var,
                     state="readonly", values=CORNER_OPTIONS, width=22).grid(
            row=0, column=0, sticky="w")

        # ── Botón iniciar/detener ──
        self.toggle_btn = ttk.Button(main, text="Iniciar", command=self._toggle)
        self.toggle_btn.grid(row=4, column=0, columnspan=2,
                             sticky="ew", pady=(4, 10))

        # ── Countdown ──
        self.countdown_var = tk.StringVar(value="")
        self.countdown_lbl = ttk.Label(
            main, textvariable=self.countdown_var,
            font=("Segoe UI", 11, "bold"), anchor="center"
        )
        self.countdown_lbl.grid(row=5, column=0, columnspan=2,
                                sticky="ew", pady=(0, 2))

        # ── Estado ──
        self.status_var = tk.StringVar(value="Detenido")
        ttk.Label(main, textvariable=self.status_var,
                  foreground="#888").grid(
            row=6, column=0, columnspan=2, sticky="w")

        # ── Registro ──
        lf = ttk.LabelFrame(main, text="Registro", padding=6)
        lf.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        self.log_text = tk.Text(
            lf, height=8, width=50, state="disabled",
            wrap="word", font=("Consolas", 9)
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        sc = ttk.Scrollbar(lf, command=self.log_text.yview)
        sc.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=sc.set)

        # ── Pie de autoría ──
        ttk.Label(
            main, text="desarrollado por CarolusDev para Macura Internacional\n2026",
            foreground="#aaa", font=("Segoe UI", 8, "italic"), anchor="center"
        ).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    # ── Estado ────────────────────────────────────────────────────────────────
    def _sync_selection(self):
        self.selected_processes = {
            BROWSERS[lbl] for lbl, var in self.browser_vars.items()
            if var.get()
        }

    def _read_interval(self) -> int | None:
        try:
            value = int(self.interval_var.get())
            if value < 1:
                raise ValueError
        except (ValueError, tk.TclError):
            return None
        unit = self.unit_var.get()
        if unit == "minutos":
            value *= 60
        elif unit == "horas":
            value *= 3600
        return value

    def _set_controls(self, running: bool):
        state_spin  = "disabled" if running else "normal"
        state_combo = "disabled" if running else "readonly"
        self.interval_spin.config(state=state_spin)
        self.unit_combo.config(state=state_combo)
        self.toggle_btn.config(text="Detener" if running else "Iniciar")

    # ── Iniciar / Detener ─────────────────────────────────────────────────────
    def _toggle(self):
        if self.worker and self.worker.is_alive():
            self._stop()
        else:
            self._start()

    def _start(self):
        self._sync_selection()
        if not self.selected_processes:
            messagebox.showwarning("Sin navegadores",
                                   "Selecciona al menos un navegador.")
            return
        interval = self._read_interval()
        if interval is None or interval < MIN_INTERVAL:
            messagebox.showwarning(
                "Intervalo inválido",
                f"El intervalo mínimo es {MIN_INTERVAL} segundos\n"
                f"(se muestra un aviso de {WARN_SECS}s antes del refresco)."
            )
            return

        self.interval_seconds = interval
        self.stop_event.clear()
        self.cancel_event.clear()
        self.postpone_event.clear()

        self.worker = threading.Thread(target=self._run_loop, daemon=True)
        self.worker.start()

        self._set_controls(running=True)
        self.status_var.set("Activo")
        self._log(f"Iniciado. Intervalo: {self.interval_seconds}s. "
                  f"Aviso: {WARN_SECS}s antes.")

    def _stop(self):
        self.stop_event.set()
        self.cancel_event.set()     # desbloquea al hilo si está esperando
        self.postpone_event.set()
        self._destroy_notifier()
        self._set_controls(running=False)
        self.countdown_var.set("")
        self.status_var.set("Detenido")
        self._log("Detenido por el usuario.")

    # ── Hilo de trabajo ───────────────────────────────────────────────────────
    def _run_loop(self):
        while not self.stop_event.is_set():
            interval = self.interval_seconds

            # ── Fase 1: Countdown normal ──────────────────────────────────
            elapsed = 0.0
            target  = float(interval - WARN_SECS)
            while elapsed < target:
                if self.stop_event.is_set():
                    return
                time.sleep(0.5)
                elapsed += 0.5
                remaining = interval - elapsed
                self._q("COUNTDOWN", remaining, "normal")

            if self.stop_event.is_set():
                return

            # ── Fase 2: Aviso (30 segundos) ───────────────────────────────
            self.cancel_event.clear()
            self.postpone_event.clear()
            self._q("SHOW_NOTIFIER", WARN_SECS)
            self._log_q(f"⚠ Aviso mostrado — refrescando en {WARN_SECS}s.")

            deadline = time.time() + WARN_SECS
            while time.time() < deadline:
                if self.stop_event.is_set():
                    self._q("HIDE_NOTIFIER")
                    return
                if self.cancel_event.is_set() or self.postpone_event.is_set():
                    break
                remaining = deadline - time.time()
                self._q("COUNTDOWN", remaining, "warn")
                time.sleep(0.5)

            self._q("HIDE_NOTIFIER")
            if self.stop_event.is_set():
                return

            # ── Evaluar resultado ─────────────────────────────────────────
            if self.postpone_event.is_set():
                self._log_q("⏸ Refresco pospuesto 5 minutos.")
                elapsed_p = 0.0
                while elapsed_p < POSTPONE_SECS:
                    if self.stop_event.is_set():
                        return
                    time.sleep(0.5)
                    elapsed_p += 0.5
                    remaining_p = POSTPONE_SECS - elapsed_p
                    self._q("COUNTDOWN", remaining_p, "postpone")
                self._log_q("▶ Postergación completada. Reiniciando ciclo.")
                continue

            if self.cancel_event.is_set():
                self._log_q("✖ Refresco cancelado. Reiniciando ciclo.")
                continue

            # Timeout sin acción → refrescar
            refresh_browsers(self.selected_processes, self._log_q)

    def _q(self, kind, *args):
        self.log_queue.put((kind, *args))

    def _log_q(self, msg):
        self.log_queue.put(("LOG", msg))

    # ── Poll (hilo principal) ─────────────────────────────────────────────────
    def _poll(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                kind = item[0]

                if kind == "LOG":
                    self._log(item[1])

                elif kind == "COUNTDOWN":
                    _, secs, phase = item
                    text = _fmt(secs)
                    if phase == "normal":
                        self.countdown_var.set(f"Próximo refresco en   {text}")
                        self.countdown_lbl.config(foreground="#27ae60")
                    elif phase == "warn":
                        self.countdown_var.set(f"⚠  Refrescando en   {text}")
                        self.countdown_lbl.config(foreground="#e74c3c")
                    elif phase == "postpone":
                        self.countdown_var.set(
                            f"Pospuesto — reactivando en   {text}")
                        self.countdown_lbl.config(foreground="#e67e22")

                elif kind == "SHOW_NOTIFIER":
                    self._show_notifier(item[1])

                elif kind == "HIDE_NOTIFIER":
                    self._destroy_notifier()

        except queue.Empty:
            pass
        self.root.after(150, self._poll)

    # ── Notifier ──────────────────────────────────────────────────────────────
    def _show_notifier(self, seconds: int):
        self._destroy_notifier()
        self.notifier = NotifierWindow(
            parent=self.root,
            seconds=seconds,
            on_cancel=self._on_user_cancel,
            on_postpone=self._on_user_postpone,
            corner=self.corner_var.get(),
        )

    def _destroy_notifier(self):
        if self.notifier:
            try:
                self.notifier.destroy()
            except Exception:
                pass
            self.notifier = None

    def _on_user_cancel(self):
        self.cancel_event.set()

    def _on_user_postpone(self):
        self.postpone_event.set()

    # ── Log ───────────────────────────────────────────────────────────────────
    def _log(self, msg: str):
        ts   = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.log_text.config(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ── Cierre ────────────────────────────────────────────────────────────────
    def _on_close(self):
        self.stop_event.set()
        self._destroy_notifier()
        self.root.destroy()


# ── Punto de entrada ──────────────────────────────────────────────────────────
def main():
    _check_expiry()
    root = tk.Tk()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # DPI awareness
    except Exception:
        pass
    RefreshBrowserApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
