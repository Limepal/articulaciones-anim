"""
scenes.py — Guion del video. Cada función agrega keyframes a la película.

La escena central (`trace_scene`) recorre, evento por evento, la traza JSON
generada por `build/ap trace`. Nada de lo que se ve en esa escena está
escrito a mano: tin, low, aristas de retroceso y articulaciones salen de la
ejecución real del algoritmo en C++.
"""
from __future__ import annotations

from collections import deque

from engine import (BG, BLUE, FAINT, GREEN, INK, MUTED, NODE_IDLE, ORANGE, PANEL, PURPLE, RED, YELLOW,
                    Movie)

GRAPH_BOX = (0.95, 1.35, 9.25, 7.3)   # región del lienzo para el grafo
PANEL_X = 10.45


def blank(movie: Movie, trans=0.6):
    movie.add({}, hold=0.15, trans=trans)


def fit_layout(pos, box=GRAPH_BOX, max_scale=1.0):
    x0, y0, x1, y1 = box
    xs, ys = [p[0] for p in pos], [p[1] for p in pos]
    w, h = (max(xs) - min(xs)) or 1.0, (max(ys) - min(ys)) or 1.0
    s = min((x1 - x0) / w, (y1 - y0) / h, max_scale)
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    return [(mx + (x - cx) * s, my + (y - cy) * s) for x, y in pos]


def text(s, x, y, size=20, color=INK, **kw):
    return dict(kind="text", s=s, x=x, y=y, size=size, color=color, **kw)


def header(title, subtitle=None):
    els = {"hdr": text(title, 0.6, 8.45, 30, INK, weight="bold")}
    if subtitle:
        els["hdr_sub"] = text(subtitle, 0.6, 7.95, 17, MUTED)
    return els


def caption(s, y=0.55):
    return {"cap": text(s, 8.0, y, 19, INK, ha="center")}


# ---------------------------------------------------------------------------
# Vista de grafo con estado del algoritmo

class GraphView:
    def __init__(self, trace, prefix="g", box=GRAPH_BOX, max_scale=1.0, r=0.36):
        self.n = trace["n"]
        self.edges = trace["edges"]
        pos = trace["pos"] or [(i, 0) for i in range(self.n)]
        self.xy = fit_layout(pos, box, max_scale)
        self.p, self.r = prefix, r
        self.reset()

    def reset(self):
        self.status = ["idle"] * self.n        # idle | active | done
        self.tin = [None] * self.n
        self.low = [None] * self.n
        self.cut = set()
        self.tree = {}          # id -> (padre, hijo)
        self.back = {}          # id -> (u, ancestro)
        self.stack = []
        self.hl_edge = None     # (id, color)
        self.flash = set()      # nodos cuyo low acaba de cambiar
        self.pulse = None       # nodo marcado como articulación en este paso
        self.dim = set()        # nodos atenuados (escena de definición)
        self.fill_override = {} # nodo -> color (escena de definición)

    # -- elementos dibujables ---------------------------------------------
    def elements(self, show_labels=True):
        p, els = self.p, {}
        for i, (u, v) in enumerate(self.edges):
            (x1, y1), (x2, y2) = self.xy[u], self.xy[v]
            dim = u in self.dim or v in self.dim
            base = dict(kind="edge", x1=x1, y1=y1, x2=x2, y2=y2, r1=self.r, r2=self.r, color=FAINT,
                        lw=3, alpha=0.12 if dim else 1.0, z=1, progress=1, grow=False)
            if self.hl_edge and self.hl_edge[0] == i:
                base.update(color=self.hl_edge[1], lw=6)
            els[f"{p}e{i}"] = base
            if i in self.tree:
                a, b = self.tree[i]
                (xa, ya), (xb, yb) = self.xy[a], self.xy[b]
                els[f"{p}t{i}"] = dict(kind="edge", x1=xa, y1=ya, x2=xb, y2=yb, r1=self.r, r2=self.r,
                                       color=INK, lw=5, z=2, progress=1)
            if i in self.back:
                a, b = self.back[i]
                (xa, ya), (xb, yb) = self.xy[a], self.xy[b]
                els[f"{p}b{i}"] = dict(kind="edge", x1=xa, y1=ya, x2=xb, y2=yb, r1=self.r, r2=self.r,
                                       color=PURPLE, lw=4, dashed=True, z=2, progress=1)
        top = self.stack[-1] if self.stack else None
        for u in range(self.n):
            x, y = self.xy[u]
            st = self.status[u]
            fill, stroke, lab = {"idle": (NODE_IDLE, MUTED, INK), "active": (YELLOW, YELLOW, BG),
                                 "done": (BLUE, BLUE, INK)}[st]
            if u in self.cut:
                fill, stroke, lab = RED, RED, INK
            if u in self.fill_override:
                fill = stroke = self.fill_override[u]
                lab = INK
            ring, ring_c, grow = 0.0, YELLOW, 0.0
            if u == top:
                ring, ring_c = 0.9, YELLOW
            if u == self.pulse:
                ring, ring_c, grow = 1.0, RED, 1.0
            els[f"{p}n{u}"] = dict(kind="node", x=x, y=y, r=self.r, fill=fill, stroke=stroke, label=str(u),
                                   label_color=lab, ring=ring, ring_color=ring_c, ring_grow=grow,
                                   alpha=0.15 if u in self.dim else 1.0, z=4)
            if show_labels and self.tin[u] is not None:
                els[f"{p}l{u}"] = text(f"tin {self.tin[u]} · low {self.low[u]}", x, y - self.r - 0.3, 15,
                                       YELLOW if u in self.flash else MUTED, ha="center", box=True, z=7)
        return els


# ---------------------------------------------------------------------------
# Panel lateral

LEGEND = [("no visitado", NODE_IDLE, MUTED), ("en la pila DFS", YELLOW, YELLOW),
          ("terminado", BLUE, BLUE), ("articulación", RED, RED)]


def panel(step, total, title, lines=(), formula=None, verdict=None, verdict_color=INK, stack=()):
    x = PANEL_X
    els = {
        "pbox": dict(kind="rect", x=x - 0.15, y=0.95, w=5.4, h=7.25, fill=PANEL, stroke=FAINT, lw=1.5, z=0),
        "pstep": text(f"Paso {step} / {total}" if total else " ", x + 5.05, 7.85, 15, MUTED, ha="right"),
        "ptitle": text(title, x + 0.1, 7.3, 21, YELLOW, weight="bold"),
        "plines": text("\n".join(lines) if lines else " ", x + 0.1, 6.55, 17, INK, va="top"),
        "pform": text(formula or " ", x + 0.1, 5.0, 20, INK),
        "pverd": text(verdict or " ", x + 0.1, 4.45, 19, verdict_color, weight="bold"),
        "pstack_lbl": text("Pila DFS (base → tope)", x + 0.1, 3.75, 15, MUTED),
    }
    for i, u in enumerate(stack):
        els[f"pst{i}"] = dict(kind="chip", x=x + 0.42 + i * 0.56, y=3.2, w=0.48, h=0.48, s=str(u),
                              fill=YELLOW if i == len(stack) - 1 else NODE_IDLE,
                              stroke=YELLOW, color=BG if i == len(stack) - 1 else INK, size=16, radius=0.08)
    for i, (name, fc, ec) in enumerate(LEGEND):
        cx, cy = x + 0.3 + (i % 2) * 2.55, 2.35 - (i // 2) * 0.48
        els[f"lg{i}"] = dict(kind="node", x=cx, y=cy, r=0.13, fill=fc, stroke=ec, label=None, lw=2, z=4)
        els[f"lgt{i}"] = text(name, cx + 0.25, cy, 14, MUTED)
    for i, (name, color, dashed) in enumerate([("arista de árbol", INK, False),
                                               ("arista de retroceso", PURPLE, True)]):
        cx, cy = x + 0.15 + i * 2.55, 1.35
        els[f"lge{i}"] = dict(kind="edge", x1=cx, y1=cy, x2=cx + 0.45, y2=cy, color=color, lw=4,
                              dashed=dashed, z=4, progress=1, grow=False)
        els[f"lget{i}"] = text(name, cx + 0.6, cy, 14, MUTED)
    return els


# ---------------------------------------------------------------------------
# Escenas

def title_scene(movie, integrantes):
    names = "   ·   ".join(integrantes)
    els = {
        "t1": text("Puntos de articulación", 8.0, 5.6, 54, INK, ha="center", weight="bold"),
        "t2": text("Cómo encontrar todos los vértices de corte con un solo DFS — O(V + E)", 8.0, 4.7, 24,
                   YELLOW, ha="center"),
        "t3": text("CS2023 Algoritmos y Estructuras de Datos · Proyecto 2: Anima tu algoritmo", 8.0, 3.2, 19,
                   MUTED, ha="center"),
        "t4": text(names, 8.0, 2.5, 20, INK, ha="center"),
    }
    movie.add(els, hold=3.2, trans=0.8, still="fig01_titulo.png")
    blank(movie)


def components_without(trace, removed):
    n = trace["n"]
    adj = [[] for _ in range(n)]
    for u, v in trace["edges"]:
        adj[u].append(v)
        adj[v].append(u)
    comp, k = [-1] * n, 0
    for s in range(n):
        if s == removed or comp[s] != -1:
            continue
        comp[s] = k
        q = deque([s])
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v != removed and comp[v] == -1:
                    comp[v] = k
                    q.append(v)
        k += 1
    return comp, k


def definition_scene(movie, trace, demo=None):
    g = GraphView(trace)
    n, m = trace["n"], len(trace["edges"])
    _, base = components_without(trace, -1)
    hdr = header("¿Qué es un punto de articulación?", "Grafo no dirigido G = (V, E)")
    side = {
        "d1": text("Un vértice es un punto de articulación\n(o vértice de corte) si al eliminarlo\n"
                   "el grafo queda con MÁS componentes\nconexas que antes.", 10.6, 6.6, 19, INK, va="top"),
    }
    movie.add({**hdr, **g.elements(), **side, **caption(f"Nuestro ejemplo: {n} vértices, {m} aristas, "
                                                         f"{base} componente conexa.")}, hold=2.8, trans=0.8)
    palette = [BLUE, GREEN, ORANGE, PURPLE]
    cut = trace["result"]["cuts"]
    if demo is None:
        non_cut = next((u for u in range(n) if u not in cut and u != 0), None)
        demo = [cut[1] if len(cut) > 1 else cut[0], non_cut] if cut else [non_cut]
    for idx, x in enumerate(demo):
        g.reset()
        g.fill_override = {x: RED}
        movie.add({**hdr, **g.elements(), **side, **caption(f"¿Qué pasa si eliminamos el vértice {x}?")},
                  hold=1.4, trans=0.6)
        comp, k = components_without(trace, x)
        g.dim = {x}
        g.fill_override = {u: palette[comp[u] % len(palette)] for u in range(n) if u != x}
        if k > base:
            msg = f"Quedan {k} componentes (antes {base})  →  {x} SÍ es punto de articulación."
        else:
            msg = f"Sigue habiendo {k} componente  →  {x} NO es punto de articulación."
        movie.add({**hdr, **g.elements(), **side, **caption(msg)}, hold=2.6, trans=0.8,
                  still="fig02_definicion.png" if idx == 0 else None)
    g.reset()
    apps = {
        "d1": text("¿Para qué sirve?", 10.6, 6.9, 21, YELLOW, weight="bold"),
        "d2": text("• Puntos únicos de falla en redes\n  (routers, servidores, subestaciones).\n"
                   "• Vulnerabilidad de redes viales\n  y de transporte.\n"
                   "• Base para componentes biconexas\n  y árboles de bloques (block-cut tree).",
                   10.6, 6.35, 17, INK, va="top"),
        "d3": text("Idea ingenua: quitar cada vértice y\ncontar componentes → O(V·(V+E)).", 10.6, 2.6, 17,
                   MUTED, va="top"),
    }
    movie.add({**hdr, **g.elements(), **apps,
               **caption("Hopcroft y Tarjan (1973): basta UN recorrido DFS → O(V + E).")}, hold=4.2, trans=0.8)
    blank(movie)


def theory_scene(movie):
    els = header("La idea: un solo DFS con tin y low")

    def mini(prefix, x0, back_above, verdict_math, verdict_txt, color):
        d = {}
        w, u, v = (x0 - 0.75, 6.85), (x0, 5.6), (x0, 4.3)
        tri = [(x0, 4.0), (x0 - 0.95, 2.35), (x0 + 0.95, 2.35)]
        d[prefix + "tri"] = dict(kind="poly", pts=tri, fill="#20262E", stroke=MUTED, lw=2, z=1)
        d[prefix + "tl"] = text("subárbol\nde v", x0, 2.85, 13, MUTED, ha="center")
        for k, (a, b) in enumerate([(w, u), (u, v)]):
            d[prefix + f"e{k}"] = dict(kind="edge", x1=a[0], y1=a[1], x2=b[0], y2=b[1], r1=0.32, r2=0.32,
                                       color=INK, lw=4, z=2, progress=1)
        if back_above:
            d[prefix + "back"] = dict(kind="edge", x1=x0 - 0.5, y1=2.75, x2=w[0], y2=w[1], r1=0, r2=0.32,
                                      color=PURPLE, lw=4, dashed=True, z=2, progress=1)
        for name, (x, y) in (("w", w), ("u", u), ("v", v)):
            fill = color if name == "u" else NODE_IDLE
            d[prefix + name] = dict(kind="node", x=x, y=y, r=0.32, fill=fill, stroke=MUTED if fill == NODE_IDLE
                                    else fill, label=name, fs=19, z=4)
        d[prefix + "vm"] = text(verdict_math, x0, 1.65, 19, INK, ha="center")
        d[prefix + "vt"] = text(verdict_txt, x0, 1.15, 16, color, ha="center", weight="bold")
        return d

    left = mini("ma", 2.0, True, r"$\mathrm{low}[v] < \mathrm{tin}[u]$", "u NO es articulación", BLUE)
    right = mini("mb", 5.4, False, r"$\mathrm{low}[v] \geq \mathrm{tin}[u]$", "u SÍ es articulación", RED)
    x = 7.6
    lines = [
        ("th1", text(r"$\mathrm{tin}[u]$: momento en que el DFS descubre u", x, 7.25, 20, INK)),
        ("th2", text(r"$\mathrm{low}[u]$: menor tin alcanzable desde el subárbol" "\nde u usando a lo más "
                     "una arista de retroceso", x, 6.35, 20, INK)),
        ("th3", text(r"$\mathrm{low}[u] = \min\{\,\mathrm{tin}[u],\ \mathrm{tin}[w]_{\,(u,w)\ retroceso},"
                     r"\ \mathrm{low}[v]_{\,v\ hijo}\,\}$", x, 5.15, 21, YELLOW)),
        ("th4", text("Regla 1 (u no es raíz): u es articulación si tiene\n" r"un hijo v con "
                     r"$\mathrm{low}[v] \geq \mathrm{tin}[u]$", x, 3.95, 20, INK)),
        ("th5", text("Regla 2 (u es raíz): es articulación si tiene\n2 o más hijos en el árbol DFS.", x, 2.7, 20,
                     INK)),
        ("th6", text("Ambas reglas se evalúan durante el mismo DFS.", x, 1.6, 17, MUTED, style="italic")),
    ]
    acc = dict(els)
    acc.update(left)
    acc.update(right)
    for i, (k, e) in enumerate(lines):
        acc[k] = e
        last = i == len(lines) - 1
        movie.add(acc, hold=4.2 if last else 2.0, trans=0.6, still="fig03_idea_tin_low.png" if last else None)
    blank(movie)


def trace_scene(movie, trace, title, subtitle, pace=1.0, prefix="g", stills=None, cap=None,
                end_hold=2.5, max_scale=1.0):
    """Anima la traza evento por evento. `stills` = {índice_evento|'done': nombre_png}."""
    stills = stills or {}
    g = GraphView(trace, prefix=prefix, max_scale=max_scale)
    events = trace["events"]
    total = len(events)
    hdr = header(title, subtitle)
    capd = caption(cap) if cap else {}
    movie.add({**hdr, **g.elements(), **capd,
               **panel(0, total, "Estado inicial", ["Ningún vértice visitado."], stack=[])},
              hold=1.2 * pace + 0.3, trans=0.7)

    for k, ev in enumerate(events, 1):
        t = ev["type"]
        g.flash, g.pulse, g.hl_edge = set(), None, None
        lines, formula, verdict, vcol, hold = [], None, None, INK, 1.0
        if t == "start":
            title_ev = f"DFS desde la raíz {ev['root']}"
            lines = ["Comienza un recorrido en profundidad."]
            if ev["component"] > 1:
                lines = [f"Componente {ev['component']}: hay vértices sin", "visitar → nueva raíz."]
            hold = 1.0
        elif t == "visit":
            u = ev["u"]
            g.status[u], g.tin[u], g.low[u] = "active", ev["tin"], ev["low"]
            g.stack.append(u)
            g.flash = {u}
            title_ev = f"Visitamos {u}"
            lines = ["Recibe el siguiente tiempo de", "descubrimiento; low empieza igual."]
            formula = rf"$\mathrm{{tin}}[{u}] = \mathrm{{low}}[{u}] = {ev['tin']}$"
            hold = 0.9
        elif t == "tree_edge":
            u, v = ev["u"], ev["v"]
            g.tree[ev["edge"]] = (u, v)
            g.hl_edge = (ev["edge"], YELLOW)
            title_ev = f"Arista de árbol {u} → {v}"
            lines = [f"{v} no ha sido visitado:", "el DFS desciende hacia él."]
            hold = 0.7
        elif t == "skip_parent":
            g.hl_edge = (ev["edge"], MUTED)
            title_ev = f"{ev['u']} → {ev['v']}: arista al padre"
            lines = ["Es la arista por la que llegamos;", "no cuenta como retroceso."]
            hold = 0.45
        elif t == "back_edge":
            u, v = ev["u"], ev["v"]
            g.back[ev["edge"]] = (u, v)
            g.low[u] = ev["low_after"]
            g.flash = {u}
            title_ev = f"Arista de retroceso {u} ⇢ {v}"
            lines = [f"{v} es un ancestro de {u} que sigue", "en la pila: el subárbol 'escapa'."]
            formula = (rf"$\mathrm{{low}}[{u}] = \min({ev['low_before']},\ \mathrm{{tin}}[{v}]) = "
                       rf"{ev['low_after']}$")
            hold = 1.5
        elif t == "seen_descendant":
            g.hl_edge = (ev["edge"], MUTED)
            title_ev = f"{ev['u']} → {ev['v']}: ya procesada"
            lines = [f"{ev['v']} es un descendiente terminado;", "esa arista ya se usó desde él."]
            hold = 0.45
        elif t == "finish":
            u = ev["u"]
            g.status[u] = "done"
            if g.stack and g.stack[-1] == u:
                g.stack.pop()
            title_ev = f"{u} terminado"
            lines = ["Se revisaron todos sus vecinos.", f"low[{u}] = {ev['low']} ya es definitivo."]
            hold = 0.7
        elif t == "return":
            u, c = ev["u"], ev["child"]
            g.low[u] = ev["low_after"]
            if ev["low_after"] != ev["low_before"]:
                g.flash = {u}
            title_ev = f"Regresamos de {c} a {u}"
            lines = [f"{u} hereda lo que su hijo {c} alcanza."]
            formula = (rf"$\mathrm{{low}}[{u}] = \min({ev['low_before']},\ \mathrm{{low}}[{c}]) = "
                       rf"{ev['low_after']}$")
            if ev["is_root"]:
                verdict, vcol = f"{u} es la raíz: se evalúa al final.", MUTED
            elif ev["condition"]:
                verdict = (rf"$\mathrm{{low}}[{c}]={ev['low_child']} \geq \mathrm{{tin}}[{u}]={ev['tin_u']}$"
                           f"  → corte")
                vcol = RED
            else:
                verdict = (rf"$\mathrm{{low}}[{c}]={ev['low_child']} < \mathrm{{tin}}[{u}]={ev['tin_u']}$"
                           f"  → sin corte")
                vcol = GREEN
            hold = 1.5
        elif t == "mark_cut":
            u = ev["u"]
            g.cut.add(u)
            g.pulse = u
            title_ev = f"¡{u} es punto de articulación!"
            if ev["child"] == -1:
                lines = ["La raíz tiene 2 o más hijos", "en el árbol DFS (Regla 2)."]
            else:
                lines = [f"Nada en el subárbol de {ev['child']} sube", f"por encima de {u} (Regla 1)."]
            hold = 1.5 if ev["first"] else 0.8
        elif t == "root_check":
            r, ch = ev["root"], ev["children"]
            title_ev = f"Regla de la raíz ({r})"
            lines = [f"La raíz tiene {ch} hijo{'s' if ch != 1 else ''} en el árbol DFS."]
            if ev["is_cut"]:
                verdict, vcol = "2 o más hijos → es articulación", RED
            else:
                verdict, vcol = "menos de 2 hijos → NO es articulación", GREEN
            hold = 1.6
        elif t == "done":
            cuts = ev["cuts"]
            title_ev = "Resultado"
            lines = [("Articulaciones: {" + ", ".join(map(str, cuts)) + "}") if cuts
                     else "No hay puntos de articulación.",
                     f"Componentes conexas: {ev['components']}",
                     "Verificado contra fuerza bruta."]
            hold = end_hold
        else:
            continue
        state = {**hdr, **g.elements(), **capd,
                 **panel(k, total, title_ev, lines, formula, verdict, vcol, stack=list(g.stack))}
        key = "done" if t == "done" else k
        movie.add(state, hold=hold * pace, trans=0.45 * min(1.0, pace + 0.3), still=stills.get(key))
    blank(movie)


def complexity_scene(movie, bench):
    hdr = header("Análisis de complejidad", "Por qué un solo DFS basta: O(V + E)")
    items = [
        ("c1", "Cada vértice se descubre y termina una sola vez → O(V)."),
        ("c2", "Cada arista {u, v} se examina dos veces,\nuna desde cada extremo → O(E)."),
        ("c3", "tin, low, padre y la pila: memoria extra O(V)."),
        ("c4", "Fuerza bruta (quitar cada vértice y\nrecorrer): O(V·(V + E))."),
        ("c5", "Peor caso de profundidad: un camino de V\nvértices → pila de altura V. Por eso usamos\n"
               "una pila explícita y no recursión."),
    ]
    tar = bench["tarjan"]
    nmax, mmax, msmax = tar["n"][-1], tar["m"][-1], tar["ms"][-1]
    fmt = lambda v: f"{v:,}".replace(",", " ")  # noqa: E731
    acc = dict(hdr)
    ys = [7.1, 6.25, 5.15, 4.4, 3.3]
    for (k, s), y in zip(items, ys):
        acc[k] = text(s, 0.6, y, 18, INK, va="top")
    acc["c0"] = text("Tiempo: O(V + E)     Memoria: O(V)", 0.6, 1.4, 24, YELLOW, weight="bold")
    chart = dict(kind="chart", x=8.6, y=1.3, w=6.6, h=6.0, progress=0.0, z=3)
    movie.add({**acc, "chart": chart}, hold=1.5, trans=0.8)
    acc["chart"] = dict(chart, progress=1.0)
    acc["c6"] = text(f"Medido: n = {fmt(nmax)}, m = {fmt(mmax)} en {msmax:.0f} ms", 11.9, 7.75, 16, MUTED,
                     ha="center")
    movie.add(acc, hold=6.5, trans=2.2, still="fig10_complejidad.png")
    blank(movie)


def credits_scene(movie, integrantes):
    els = {
        "k1": text("Puntos de articulación", 8.0, 7.0, 40, INK, ha="center", weight="bold"),
        "k2": text("Integrantes", 8.0, 5.9, 20, YELLOW, ha="center"),
        "k3": text("\n".join(integrantes), 8.0, 5.05, 20, INK, ha="center", va="top"),
        "k4": text("Implementación propia en C++17 (DFS iterativo + traza JSON) · Animación: Python, "
                   "Matplotlib y FFmpeg", 8.0, 2.6, 15, MUTED, ha="center"),
        "k5": text("Referencias: Hopcroft & Tarjan (1973), Comm. ACM 16(6) · Cormen et al., Introduction to "
                   "Algorithms · Estilo inspirado en 3Blue1Brown / Manim", 8.0, 2.05, 13, MUTED, ha="center"),
        "k6": text("CS2023 Algoritmos y Estructuras de Datos · 2026-2", 8.0, 1.3, 15, MUTED, ha="center"),
    }
    movie.add(els, hold=4.5, trans=0.8, still="fig11_creditos.png")
    blank(movie, trans=0.8)
