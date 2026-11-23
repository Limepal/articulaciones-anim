// articulation.hpp
// Puntos de articulación (cut vertices) con el algoritmo de Hopcroft–Tarjan:
// un único DFS que calcula tin[u] (tiempo de descubrimiento) y low[u]
// (el menor tin alcanzable desde el subárbol de u usando a lo más una arista
// de retroceso). Complejidad O(|V| + |E|) en tiempo y O(|V|) memoria extra.
#pragma once
#include <vector>

#include "graph.hpp"
#include "trace.hpp"

class ArticulationFinder {
public:
    // trace == nullptr  -> ejecución "silenciosa" (benchmark).
    // trace != nullptr  -> se registra cada paso para la animación.
    explicit ArticulationFinder(const Graph& g, TraceWriter* trace = nullptr);

    // Ejecuta el DFS desde todos los vértices no visitados (cubre grafos
    // desconexos) y devuelve los puntos de articulación en orden creciente.
    std::vector<int> run();

    const std::vector<int>& tin() const { return tin_; }
    const std::vector<int>& low() const { return low_; }
    const std::vector<int>& parent() const { return parent_; }
    int components() const { return components_; }

private:
    void dfsFrom(int root);

    const Graph& g_;
    TraceWriter* trace_;
    std::vector<int> tin_, low_, parent_;
    std::vector<char> isCut_;
    int timer_ = 0;
    int components_ = 0;
};

// Verificador por fuerza bruta: quita cada vértice y cuenta componentes.
// O(|V| * (|V| + |E|)). Sirve para probar la versión eficiente y como
// referencia en el análisis empírico de complejidad.
std::vector<int> articulationBruteForce(const Graph& g);
int countComponents(const Graph& g, int removed = -1);
