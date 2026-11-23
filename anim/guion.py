"""
guion.py — Narración del video para UNA sola persona.

Cada escena se divide en segmentos (n_keyframes, texto). render.py ajusta la
duración de esos keyframes para que coincida con el tiempo que toma leer el
texto en voz alta, y exporta el guion con sus marcas de tiempo
(out/guion_video.md). Si cambian el texto, el video se re-sincroniza solo.
"""

WPS = 2.4        # palabras por segundo (~144 palabras/min, ritmo de exposición)
PAUSA = 0.5      # respiro al final de cada segmento (s)

GUION = [
    ("titulo", "Título", [
        (2, "Hola. En nombre de nuestro equipo, Gabriel Díaz y Brisseth Surquislla, les presento cómo encontrar "
            "los puntos de articulación de un grafo con un solo DFS."),
    ]),
    ("definicion", "¿Qué es un punto de articulación?", [
        (1, "Tomemos un grafo no dirigido. Un punto de articulación es un vértice que, al eliminarlo, deja al "
            "grafo con más componentes conexas que antes."),
        (2, "Si quitamos el vértice 3, el grafo se parte en dos: el 3 es un punto de articulación."),
        (2, "Si quitamos el 4, todo sigue conectado: el 4 no lo es."),
        (2, "Sirven para detectar puntos únicos de falla en redes de comunicación o de transporte. "
            "Probar vértice por vértice cuesta V por V más E; Hopcroft y Tarjan lo resolvieron con un solo DFS."),
    ]),
    ("teoria", "La idea: tin y low", [
        (1, "La idea usa dos números por vértice. tin es el momento en que el DFS lo descubre."),
        (1, "low es el menor tin al que se puede llegar desde su subárbol usando, como máximo, una arista de "
            "retroceso."),
        (1, "Se calcula como el mínimo entre su propio tin, el tin de los ancestros a los que apunta y el low de "
            "sus hijos."),
        (1, "Regla uno: un vértice que no es la raíz es articulación si tiene un hijo v con low de v mayor o "
            "igual que su tin. Como en el dibujo de la derecha: nada del subárbol sube por encima de u."),
        (1, "Regla dos: la raíz es articulación solo si tiene dos o más hijos en el árbol DFS."),
        (2, "Y ambas reglas se revisan en el mismo recorrido."),
    ]),
    ("ejecucion", "Ejecución paso a paso", [
        (5, "Veamos la ejecución. Cada cuadro sale de la traza de nuestro programa en C++. Empezamos en el 0, "
            "con tin y low igual a cero, y bajamos al 1."),
        (7, "Del 1 pasamos al 2, que tiene una arista de retroceso al 0: low de 2 baja a 0. Al regresar al 1, "
            "low de 2 es menor que tin de 1, así que no hay corte."),
        (20, "El DFS cruza al 3, al 4 y al 5. La arista de retroceso del 5 al 3 baja low de 5 a 3. Luego avanza "
             "al 6, al 7 y al 8, donde otra arista de retroceso deja low de 8 en 6."),
        (7, "Al volver del 7 al 6, low de 7 es 6, igual a tin de 6. Nada del subárbol sube por encima del 6: es "
            "nuestro primer punto de articulación."),
        (9, "El 5 también lo es. El 4 no, porque low de 5 es 3, menor que 4: la arista del 5 al 3 lo rodea. "
            "Al volver al 3, low de 4 es igual a su tin, así que el 3 es articulación."),
        (9, "El 1 también cumple la regla. La raíz tiene un solo hijo, así que no es articulación. Resultado: "
            "1, 3, 5 y 6, igual que la fuerza bruta."),
    ]),
    ("raiz_triangulo", "Caso borde 1: la raíz con un hijo", [
        (19, "Primer caso borde: la raíz. Como su tin es cero, la regla uno siempre se cumpliría. En este "
             "triángulo, la raíz tiene un solo hijo en el árbol DFS, así que no es articulación."),
    ]),
    ("raiz_mono", "Caso borde 1: la raíz con dos hijos", [
        (32, "En cambio, en estos dos triángulos unidos por el 0, la raíz tiene dos hijos. Sus subárboles solo "
             "se conectan a través de ella, y por eso sí es punto de articulación."),
    ]),
    ("ciclo", "Caso borde 2: un ciclo", [
        (34, "Segundo caso: un ciclo. La arista de retroceso del 5 al 0 baja todos los low a cero. Todo vértice "
             "tiene un camino alternativo, así que no hay articulaciones."),
    ]),
    ("desconexo", "Caso borde 3: grafo desconexo", [
        (31, "Tercer caso: un grafo desconexo. El algoritmo lanza un DFS por cada componente. Solo el 1 es "
             "articulación; quitar el vértice aislado 5 no crea componentes nuevas."),
    ]),
    ("complejidad", "Análisis de complejidad", [
        (1, "¿Cuánto cuesta? Cada vértice se descubre una sola vez, y cada arista se revisa dos veces, una por "
            "extremo."),
        (2, "El total es O de V más E en tiempo y O de V en memoria. Usamos una pila explícita para que un "
            "camino muy largo no desborde la recursión. En la práctica, un grafo de un millón de vértices se "
            "procesa en medio segundo, mientras la fuerza bruta crece de forma cuadrática."),
    ]),
    ("creditos", "Créditos", [
        (2, "Gracias por ver. El código, las pruebas y este video están en nuestro repositorio."),
    ]),
]


def palabras(texto: str) -> int:
    return len(texto.split())


def duracion(texto: str) -> float:
    return palabras(texto) / WPS + PAUSA
