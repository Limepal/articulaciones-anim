"""
engine.py — Mini motor de animación "estilo Manim" sobre Matplotlib + FFmpeg.

Idea: una escena es una lista de *keyframes*. Cada keyframe es un diccionario
{clave: elemento}, donde un elemento es un nodo, una arista, un texto, etc.
Entre dos keyframes consecutivos el motor interpola todo lo que se pueda
interpolar (posiciones, colores, opacidades, progreso de trazado) con una
curva suave (ease-in-out), y hace fundidos cuando un elemento aparece,
desaparece o cambia de texto. Así obtenemos transiciones fluidas sin
programar cada fotograma a mano.

El motor NO decide qué se dibuja: eso lo deciden las escenas a partir de la
traza que produce el programa C++.
"""
from __future__ import annotations

import copy
import os
import subprocess
from dataclasses import dataclass, field

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon  # noqa: E402
import numpy as np  # noqa: E402

W, H = 16.0, 9.0          # coordenadas lógicas del lienzo (16:9)
PX_W, PX_H = 1920, 1080   # resolución del video

# Paleta (fondo oscuro estilo 3Blue1Brown)
BG = "#14171C"
INK = "#ECECEC"
MUTED = "#9AA3B2"
FAINT = "#4A505C"
YELLOW = "#E5C05C"
BLUE = "#2E95B5"
RED = "#E0565B"
PURPLE = "#C792EA"
GREEN = "#7BC67E"
ORANGE = "#D7743A"
NODE_IDLE = "#2A2F38"
PANEL = "#1B1F26"

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["mathtext.fontset"] = "dejavusans"


# ---------------------------------------------------------------------------
# Interpolación

def ease(t: float) -> float:
    """Curva suave tipo 'smooth' de Manim (cúbica ease-in-out)."""
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_to_hex(c):
    return "#" + "".join(f"{int(round(max(0, min(1, x)) * 255)):02x}" for x in c)


def _is_color(v) -> bool:
    return isinstance(v, str) and len(v) == 7 and v.startswith("#")


def _lerp_value(a, b, t):
    if isinstance(a, bool) or isinstance(b, bool):
        return b if t >= 0.5 else a
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * t
    if _is_color(a) and _is_color(b):
        ca, cb = _hex_to_rgb(a), _hex_to_rgb(b)
        return _rgb_to_hex([x + (y - x) * t for x, y in zip(ca, cb)])
    return b if t >= 0.5 else a


def interpolate(prev: dict, cur: dict, t: float) -> list:
    """Devuelve la lista de elementos a dibujar en el instante t ∈ [0, 1]."""
    out = []
    for key in list(prev.keys()) + [k for k in cur.keys() if k not in prev]:
        a, b = prev.get(key), cur.get(key)
        if a is not None and b is not None:
            if a.get("kind") == b.get("kind") == "text" and a.get("s") != b.get("s"):
                # Cambio de texto: fundido cruzado.
                ea = dict(a, alpha=a.get("alpha", 1) * (1 - t))
                eb = dict(b, alpha=b.get("alpha", 1) * t)
                out += [ea, eb]
                continue
            e = {k: _lerp_value(a.get(k, b[k]), b[k], t) for k in b}
            out.append(e)
        elif b is not None:
            e = dict(b)
            if "progress" in b and b.get("grow", True):
                e["progress"] = b["progress"] * t          # se "dibuja" la arista
            else:
                e["alpha"] = b.get("alpha", 1) * t
                if e.get("kind") == "node":
                    e["r"] = b["r"] * (0.6 + 0.4 * t)
            out.append(e)
        else:
            e = dict(a)
            e["alpha"] = a.get("alpha", 1) * (1 - t)
            out.append(e)
    out.sort(key=lambda e: e.get("z", 0))
    return out


# ---------------------------------------------------------------------------
# Dibujo

class Canvas:
    def __init__(self, chart_data=None):
        self.fig = plt.figure(figsize=(PX_W / 100, PX_H / 100), dpi=100, facecolor=BG)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.chart_data = chart_data

    def _reset(self):
        for extra in self.fig.axes[1:]:
            extra.remove()
        ax = self.ax
        ax.cla()
        ax.set_xlim(0, W)
        ax.set_ylim(0, H)
        ax.set_facecolor(BG)
        ax.axis("off")

    def draw(self, elements: list) -> np.ndarray:
        self._reset()
        for e in elements:
            if e.get("alpha", 1) <= 0.003:
                continue
            getattr(self, "_draw_" + e["kind"])(e)
        self.fig.canvas.draw()
        buf = np.asarray(self.fig.canvas.buffer_rgba())
        return buf[:, :, :3].copy()

    # -- primitivas ---------------------------------------------------------
    def _draw_node(self, e):
        a = e.get("alpha", 1)
        if e.get("ring", 0) > 0.01:
            self.ax.add_patch(Circle((e["x"], e["y"]), e["r"] + 0.12 + 0.25 * e.get("ring_grow", 0),
                                     fill=False, ec=e.get("ring_color", RED), lw=4,
                                     alpha=a * e["ring"], zorder=3))
        self.ax.add_patch(Circle((e["x"], e["y"]), e["r"], fc=e["fill"], ec=e["stroke"],
                                 lw=e.get("lw", 3), alpha=a, zorder=4))
        if e.get("label") is not None:
            self.ax.text(e["x"], e["y"], str(e["label"]), ha="center", va="center",
                         fontsize=e.get("fs", 22), color=e.get("label_color", INK), weight="bold",
                         alpha=a, zorder=5)

    def _draw_edge(self, e):
        x1, y1, x2, y2 = e["x1"], e["y1"], e["x2"], e["y2"]
        d = np.hypot(x2 - x1, y2 - y1) or 1.0
        ux, uy = (x2 - x1) / d, (y2 - y1) / d
        r1, r2 = e.get("r1", 0), e.get("r2", 0)
        sx, sy = x1 + ux * r1, y1 + uy * r1
        ex, ey = x2 - ux * r2, y2 - uy * r2
        p = e.get("progress", 1)
        ex, ey = sx + (ex - sx) * p, sy + (ey - sy) * p
        if p <= 0.001:
            return
        self.ax.plot([sx, ex], [sy, ey], color=e["color"], lw=e.get("lw", 3), alpha=e.get("alpha", 1),
                     ls=(0, (4, 3)) if e.get("dashed") else "-", solid_capstyle="round",
                     dash_capstyle="round", zorder=e.get("z", 1))

    def _draw_text(self, e):
        kw = {}
        if e.get("box"):
            kw["bbox"] = dict(boxstyle="round,pad=0.25", fc=BG, ec="none", alpha=0.85 * e.get("alpha", 1))
        self.ax.text(e["x"], e["y"], e["s"], fontsize=e.get("size", 20), color=e.get("color", INK),
                     ha=e.get("ha", "left"), va=e.get("va", "center"), weight=e.get("weight", "normal"),
                     alpha=e.get("alpha", 1), zorder=e.get("z", 6), linespacing=1.35,
                     style=e.get("style", "normal"), **kw)

    def _draw_rect(self, e):
        self.ax.add_patch(FancyBboxPatch((e["x"], e["y"]), e["w"], e["h"],
                                         boxstyle=f"round,pad=0,rounding_size={e.get('radius', 0.15)}",
                                         fc=e.get("fill", "none"), ec=e.get("stroke", "none"),
                                         lw=e.get("lw", 1.5), alpha=e.get("alpha", 1), zorder=e.get("z", 0)))

    def _draw_chip(self, e):
        self._draw_rect(dict(e, x=e["x"] - e["w"] / 2, y=e["y"] - e["h"] / 2, z=e.get("z", 5)))
        self.ax.text(e["x"], e["y"], e["s"], ha="center", va="center", fontsize=e.get("size", 18),
                     color=e.get("color", INK), weight="bold", alpha=e.get("alpha", 1), zorder=e.get("z", 5) + 1)

    def _draw_poly(self, e):
        self.ax.add_patch(Polygon(e["pts"], closed=True, fc=e.get("fill", "none"), ec=e.get("stroke", MUTED),
                                  lw=e.get("lw", 2), alpha=e.get("alpha", 1), zorder=e.get("z", 1)))

    def _draw_chart(self, e):
        """Gráfico log-log de los tiempos medidos por `ap bench`."""
        data = self.chart_data
        x0, y0, w, h = e["x"], e["y"], e["w"], e["h"]
        ax = self.fig.add_axes([x0 / W, y0 / H, w / W, h / H])
        ax.set_facecolor(BG)
        a, p = e.get("alpha", 1), e.get("progress", 1)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(MUTED)
            ax.spines[side].set_alpha(a)
        ax.tick_params(colors=MUTED, labelsize=15)
        ax.set_xscale("log")
        ax.set_yscale("log")
        allx = [x for s in data.values() for x in s["n"]]
        ally = [y for s in data.values() for y in s["ms"]]
        ax.set_xlim(min(allx) / 1.5, max(allx) * 1.6)
        ax.set_ylim(min(ally) / 2, max(ally) * 2.5)
        ax.grid(True, which="major", color=FAINT, alpha=0.35 * a, lw=0.8)
        ax.set_xlabel("vértices n  (aristas m ≈ 3n)", color=MUTED, fontsize=16, alpha=a)
        ax.set_ylabel("tiempo (ms)", color=MUTED, fontsize=16, alpha=a)
        for lab in ax.get_xticklabels() + ax.get_yticklabels():
            lab.set_alpha(a)
        for name, s in data.items():
            k = max(1, int(round(p * len(s["n"]))))
            xs, ys = s["n"][:k], s["ms"][:k]
            ax.plot(xs, ys, color=s["color"], lw=3, alpha=a, marker="o", ms=8,
                    markeredgecolor=BG, markeredgewidth=2)
            if p >= 0.999:
                ax.annotate(s["label"], (xs[-1], ys[-1]), xytext=(-14, 10), textcoords="offset points",
                            color=INK, fontsize=16, ha="right", va="bottom", alpha=a)


# ---------------------------------------------------------------------------
# Película

@dataclass
class Keyframe:
    state: dict
    hold: float
    trans: float
    still: str | None = None


@dataclass
class Movie:
    fps: int = 30
    frames: list = field(default_factory=list)

    def add(self, state: dict, hold: float = 1.0, trans: float = 0.5, still: str | None = None):
        self.frames.append(Keyframe(copy.deepcopy(state), hold, trans, still))

    def duration(self) -> float:
        return sum(k.hold + k.trans for k in self.frames)

    def render(self, out_path: str | None, chart_data=None, stills_dir: str | None = None,
               stills_only: bool = False, crf: int = 18):
        canvas = Canvas(chart_data)
        proc = None
        if not stills_only:
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            proc = subprocess.Popen(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", f"{PX_W}x{PX_H}", "-r", str(self.fps), "-i", "-",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path],
                stdin=subprocess.PIPE)
        if stills_dir:
            os.makedirs(stills_dir, exist_ok=True)
        prev: dict = {}
        total = 0
        for i, kf in enumerate(self.frames):
            if not stills_only:
                nt = max(1, int(round(kf.trans * self.fps)))
                for j in range(1, nt + 1):
                    proc.stdin.write(canvas.draw(interpolate(prev, kf.state, ease(j / nt))).tobytes())
                    total += 1
            if kf.still or not stills_only:
                img = canvas.draw(interpolate(prev, kf.state, 1.0))
                if kf.still and stills_dir:
                    plt.imsave(os.path.join(stills_dir, kf.still), img)
                if not stills_only:
                    nh = int(round(kf.hold * self.fps))
                    raw = img.tobytes()
                    for _ in range(nh):
                        proc.stdin.write(raw)
                    total += nh
            prev = kf.state
            if (i + 1) % 25 == 0:
                print(f"  keyframe {i + 1}/{len(self.frames)}", flush=True)
        if proc:
            proc.stdin.close()
            proc.wait()
        return total
