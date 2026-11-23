// graph.hpp
// Grafo no dirigido representado con listas de adyacencia.
// Cada entrada de la lista guarda (vecino, id_de_arista). Guardar el id de la
// arista (y no solo el vecino) permite distinguir aristas paralelas y saltar
// exactamente la arista por la que se llegó a un nodo en el DFS.
#pragma once
#include <stdexcept>
#include <utility>
#include <vector>

struct Graph {
    int n = 0;                                      // número de vértices (0..n-1)
    std::vector<std::vector<std::pair<int, int>>> adj; // adj[u] = {(v, id), ...}
    std::vector<std::pair<int, int>> edges;         // edges[id] = (u, v)
    std::vector<std::pair<double, double>> pos;     // posiciones opcionales (solo para dibujar)

    Graph() = default;
    explicit Graph(int n_) : n(n_), adj(n_) {}

    int addEdge(int u, int v) {
        if (u < 0 || v < 0 || u >= n || v >= n)
            throw std::out_of_range("vertice fuera de rango");
        int id = static_cast<int>(edges.size());
        edges.emplace_back(u, v);
        adj[u].emplace_back(v, id);
        adj[v].emplace_back(u, id);   // no dirigido: la arista aparece en ambas listas
        return id;
    }

    int m() const { return static_cast<int>(edges.size()); }
};
