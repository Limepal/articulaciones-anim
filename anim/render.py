"""
render.py — Arma el video completo a partir de las trazas del programa C++.

Uso:
  python3 anim/render.py --traces out/traces --bench out/bench.csv --out out/articulaciones.mp4
  python3 anim/render.py ... --stills-only --stills-dir out/figuras   (solo capturas PNG)
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import BLUE, ORANGE, Movie  # noqa: E402
import guion  # noqa: E402
import scenes  # noqa: E402


def load_bench(path):
    data = {"tarjan": {"n": [], "m": [], "ms": [], "color": BLUE, "label": "Hopcroft–Tarjan"},
            "fuerza_bruta": {"n": [], "m": [], "ms": [], "color": ORANGE, "label": "Fuerza bruta"}}
    with open(path) as f:
        for row in csv.DictReader(f):
            s = data[row["algoritmo"]]
            s["n"].append(int(row["n"]))
            s["m"].append(int(row["m"]))
            s["ms"].append(float(row["ms"]))
    return data


def first_index(events, pred):
    for i, ev in enumerate(events, 1):
        if pred(ev):
            return i
    return None


def build(movie, traces, bench, integrantes):
    """Arma las escenas y devuelve el índice del primer keyframe de cada una."""
    marks = []
    mark = lambda: marks.append(len(movie.frames))  # noqa: E731
    main = traces["ejemplo_principal"]
    mark()
    scenes.title_scene(movie, integrantes)
    mark()
    scenes.definition_scene(movie, main, demo=[3, 4])
    mark()
    scenes.theory_scene(movie)
    ev = main["events"]
    mark()
    scenes.trace_scene(
        movie, main, "Ejecución paso a paso",
        "Cada cuadro sale de la traza que genera nuestro programa en C++", pace=0.8,
        stills={first_index(ev, lambda e: e["type"] == "return" and e["condition"]): "fig04_dfs_en_progreso.png",
                "done": "fig05_resultado_final.png"})
    tri = traces["caso_raiz_triangulo"]
    mark()
    scenes.trace_scene(
        movie, tri, "Caso borde 1: ¿por qué la raíz es especial?",
        "Si la raíz tiene tin = 0, siempre se cumple low[v] ≥ tin[raíz]",
        pace=0.34, prefix="c1", max_scale=0.75, end_hold=2.8,
        cap="Triángulo: la raíz tiene un solo hijo en el árbol DFS → no es articulación.",
        stills={first_index(tri["events"], lambda e: e["type"] == "root_check"): "fig06_raiz_un_hijo.png"})
    mark()
    scenes.trace_scene(
        movie, traces["caso_raiz_mono"], "Caso borde 1: ¿por qué la raíz es especial?",
        "Dos triángulos unidos por la raíz 0",
        pace=0.30, prefix="c2", max_scale=0.75, end_hold=2.8,
        cap="Aquí la raíz tiene dos hijos: sus subárboles solo se conectan a través de ella.",
        stills={"done": "fig07_raiz_dos_hijos.png"})
    mark()
    scenes.trace_scene(
        movie, traces["caso_ciclo"], "Caso borde 2: un ciclo",
        "Todo vértice tiene un camino alternativo",
        pace=0.24, prefix="c3", max_scale=0.75, end_hold=2.5,
        cap="La arista de retroceso 5 ⇢ 0 baja todos los low a 0: no hay articulaciones.",
        stills={"done": "fig08_ciclo.png"})
    mark()
    scenes.trace_scene(
        movie, traces["caso_desconexo"], "Caso borde 3: grafo desconexo y vértice aislado",
        "El algoritmo lanza un DFS por cada componente",
        pace=0.26, prefix="c4", max_scale=0.75, end_hold=3.0,
        cap="Tres raíces. El vértice aislado 5 no tiene hijos: quitarlo no crea componentes nuevas.",
        stills={"done": "fig09_desconexo.png"})
    mark()
    scenes.complexity_scene(movie, bench)
    mark()
    scenes.credits_scene(movie, integrantes)
    marks.append(len(movie.frames))
    return marks


def fmt_t(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def sync_to_script(movie, marks, out_md):
    """Ajusta los holds de cada segmento para que dure lo que su narración y exporta el guion."""
    assert len(marks) - 1 == len(guion.GUION), "número de escenas distinto al del guion"
    for (sid, _, segs), a, b in zip(guion.GUION, marks, marks[1:]):
        assert sum(n for n, _ in segs) == b - a, f"{sid}: {b - a} keyframes, guion suma {sum(n for n, _ in segs)}"
    idx = 0
    for _, _, segs in guion.GUION:
        for n, texto in segs:
            kfs = movie.frames[idx:idx + n]
            target = guion.duracion(texto)
            trans = sum(k.trans for k in kfs)
            holds = sum(k.hold for k in kfs)
            if target > trans:
                for k in kfs:
                    k.hold = (k.hold / holds * (target - trans)) if holds > 0 else (target - trans) / n
            else:  # el texto es más corto que la animación mínima: se acortan transiciones
                for k in kfs:
                    k.trans *= target / trans
                    k.hold = 0.0
            idx += n
    # Exportar guion con marcas de tiempo reales del video
    t, idx, lines = 0.0, 0, []
    lines.append("# Guion del video — Puntos de articulación\n")
    lines.append(f"Narración para una sola persona · ritmo ≈ {round(guion.WPS * 60)} palabras/min · "
                 f"duración total {fmt_t(movie.duration())}\n")
    for sid, titulo, segs in guion.GUION:
        lines.append(f"\n## {titulo}\n")
        for n, texto in segs:
            dur = sum(k.trans + k.hold for k in movie.frames[idx:idx + n])
            lines.append(f"- **[{fmt_t(t)} – {fmt_t(t + dur)}]** {texto}")
            t += dur
            idx += n
    with open(out_md, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traces", default="out/traces")
    ap.add_argument("--bench", default="out/bench.csv")
    ap.add_argument("--out", default="out/articulaciones.mp4")
    ap.add_argument("--stills-dir", default="out/figuras")
    ap.add_argument("--stills-only", action="store_true")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--guion", default="out/guion_video.md")
    ap.add_argument("--no-sync", action="store_true", help="no ajustar la duración al guion narrado")
    ap.add_argument("--integrantes", default="Gabriel Díaz;Brisseth Surquislla",
                    help="nombres separados por ';'")
    args = ap.parse_args()

    traces = {}
    for name in os.listdir(args.traces):
        if name.endswith(".json"):
            with open(os.path.join(args.traces, name)) as f:
                traces[name[:-5]] = json.load(f)
    bench = load_bench(args.bench)
    movie = Movie(fps=args.fps)
    marks = build(movie, traces, bench, [s.strip() for s in args.integrantes.split(";") if s.strip()])
    if not args.no_sync:
        sync_to_script(movie, marks, args.guion)
    print(f"{len(movie.frames)} keyframes, duración ≈ {movie.duration():.1f} s")
    n = movie.render(args.out, chart_data=bench, stills_dir=args.stills_dir, stills_only=args.stills_only)
    if not args.stills_only:
        print(f"Video: {args.out} ({n} cuadros)")
    print(f"Capturas: {args.stills_dir}")


if __name__ == "__main__":
    main()
