# Puntos de articulación — Anima tu algoritmo

Proyecto 2 del curso **CS2023 Algoritmos y Estructuras de Datos** (UTEC, 2026-2).
Video educativo que explica y anima el algoritmo de **Hopcroft–Tarjan** para encontrar
todos los puntos de articulación (vértices de corte) de un grafo no dirigido en **O(V + E)**.

**Integrantes:** Gabriel Díaz · Brisseth Surquislla
**Video:** `out/articulaciones.mp4` · enlace: _(pegar aquí el enlace de YouTube no listado / Drive)_

## Cómo funciona (animación real, no simulada)

```
data/*.txt ──► build/ap trace (C++17) ──► out/traces/*.json ──► anim/render.py ──► out/articulaciones.mp4
 (grafo)        DFS iterativo + low        traza de eventos        Matplotlib + FFmpeg     + out/figuras/*.png
```

1. `src/` contiene la implementación propia en C++17 (grafo con listas de adyacencia y
   el DFS que calcula `tin` y `low`). No usa ninguna biblioteca de grafos.
2. Cuando se ejecuta con `trace`, el algoritmo registra cada paso (visitar, arista de árbol,
   arista de retroceso, regreso al padre, marcar articulación, regla de la raíz) en un JSON.
   Antes de escribir la traza, el resultado se compara contra una fuerza bruta.
3. `anim/render.py` lee esas trazas y dibuja cada evento. Los valores `tin`/`low`, las
   aristas y las articulaciones que se ven en el video salen de la traza, no de valores escritos a mano.

## Software requerido

| Herramienta | Versión probada |
| --- | --- |
| g++ (o clang++) con C++17 | g++ 13.3 |
| GNU Make | 4.3 |
| Python | 3.10 o superior (probado en 3.13) |
| Matplotlib, NumPy | Matplotlib 3.11 / NumPy 2.5 |
| FFmpeg (con libx264) | 6.1 |

Instalación rápida (Ubuntu/Debian):

```bash
sudo apt install g++ make ffmpeg python3-pip
pip install matplotlib numpy
```

En Windows se recomienda WSL; en macOS: `brew install ffmpeg` y `pip3 install matplotlib numpy`.

## Pasos para reproducir

```bash
make            # compila build/ap
make test       # 5008 pruebas: Tarjan vs fuerza bruta (incluye casos borde)
make traces     # genera out/traces/*.json a partir de data/*.txt
make bench      # mide tiempos -> out/bench.csv (≈ 10 s)
make video      # out/articulaciones.mp4 (1920x1080, 30 fps, 4:48) + out/guion_video.md
make stills     # solo las capturas PNG en out/figuras/
```

Para poner los nombres reales en la portada y los créditos:

```bash
python3 anim/render.py --integrantes "Nombre 1;Nombre 2;Nombre 3"
```

Comandos útiles del binario:

```bash
./build/ap run data/ejemplo_principal.txt     # imprime tin, low y articulaciones
./build/ap trace data/caso_ciclo.txt out.json # genera una traza
```

## Formato de los grafos (`data/*.txt`)

```
# comentario
n m          # vértices 0..n-1, m aristas
u v          # m líneas
pos          # opcional: n líneas "x y" con la posición de cada vértice en el dibujo
```

## Estructura del repositorio

```
src/graph.hpp          grafo no dirigido (listas de adyacencia con id de arista)
src/trace.hpp          registro de eventos y serialización JSON
src/articulation.*     Hopcroft–Tarjan iterativo + verificador por fuerza bruta
src/main.cpp           CLI: run | trace | test | bench
data/                  grafo principal y casos borde (raíz, ciclo, desconexo)
anim/engine.py         motor de keyframes con interpolación suave (estilo Manim)
anim/scenes.py         guion: título, definición, teoría, ejecución, casos borde, complejidad, créditos
anim/render.py         arma el video y lo sincroniza con el guion narrado
anim/guion.py          narración (1 persona); fija la duración de cada escena
```

## Referencias

- J. Hopcroft y R. Tarjan (1973). *Algorithm 447: Efficient algorithms for graph manipulation*. Communications of the ACM, 16(6), 372–378.
- R. Tarjan (1972). *Depth-first search and linear graph algorithms*. SIAM Journal on Computing, 1(2), 146–160.
- T. Cormen, C. Leiserson, R. Rivest y C. Stein (2009). *Introduction to Algorithms*, 3.ª ed., MIT Press (Problema 22-2).
- Estilo visual inspirado en los videos de [3Blue1Brown](https://www.3blue1brown.com/) y en [Manim](https://docs.manim.community/).
