// main.cpp — interfaz de línea de comandos.
//
//   ./ap run   <grafo.txt>              imprime tin, low y articulaciones
//   ./ap trace <grafo.txt> <salida.json> genera la traza que anima el video
//   ./ap test  [casos]                   compara contra fuerza bruta
//   ./ap bench <salida.csv>              mide tiempos (Tarjan vs fuerza bruta)
//
// Formato de <grafo.txt> (las líneas que empiezan con # se ignoran):
//   n m
//   u1 v1
//   ...            (m aristas, vértices 0..n-1)
//   pos            (opcional) seguido de n líneas "x y" para el dibujo
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <random>
#include <sstream>
#include <string>

#include "articulation.hpp"
#include "graph.hpp"
#include "trace.hpp"

namespace {

Graph readGraph(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("no se pudo abrir " + path);
    std::stringstream clean;
    std::string line;
    while (std::getline(in, line)) {
        auto first = line.find_first_not_of(" \t\r");
        if (first == std::string::npos || line[first] == '#') continue;
        clean << line << '\n';
    }
    int n, m;
    if (!(clean >> n >> m)) throw std::runtime_error("cabecera 'n m' invalida");
    Graph g(n);
    for (int i = 0; i < m; ++i) {
        int u, v;
        clean >> u >> v;
        g.addEdge(u, v);
    }
    std::string tag;
    if (clean >> tag && tag == "pos") {
        g.pos.resize(n);
        for (int i = 0; i < n; ++i) clean >> g.pos[i].first >> g.pos[i].second;
    }
    return g;
}

void writeTraceJson(const Graph& g, const ArticulationFinder& f, const std::vector<int>& cuts,
                    const TraceWriter& tw, std::ostream& os) {
    auto vec = [&](const std::vector<int>& v) {
        std::string s = "[";
        for (size_t i = 0; i < v.size(); ++i) s += (i ? "," : "") + std::to_string(v[i]);
        return s + "]";
    };
    os << "{\n\"n\": " << g.n << ",\n\"edges\": [";
    for (int i = 0; i < g.m(); ++i)
        os << (i ? "," : "") << "[" << g.edges[i].first << "," << g.edges[i].second << "]";
    os << "],\n\"pos\": ";
    if (g.pos.empty()) {
        os << "null";
    } else {
        os << "[";
        for (int i = 0; i < g.n; ++i) os << (i ? "," : "") << "[" << g.pos[i].first << "," << g.pos[i].second << "]";
        os << "]";
    }
    os << ",\n\"result\": {\"cuts\": " << vec(cuts) << ", \"tin\": " << vec(f.tin()) << ", \"low\": " << vec(f.low())
       << ", \"parent\": " << vec(f.parent()) << ", \"components\": " << f.components() << "},\n";
    os << "\"events\": ";
    tw.writeArray(os);
    os << "\n}\n";
}

Graph randomGraph(int n, int extraEdges, bool connected, std::mt19937& rng) {
    Graph g(n);
    if (n == 0) return g;
    if (connected)
        for (int v = 1; v < n; ++v) g.addEdge(std::uniform_int_distribution<int>(0, v - 1)(rng), v);
    std::uniform_int_distribution<int> pick(0, n - 1);
    for (int i = 0; i < extraEdges; ++i) {
        int u = pick(rng), v = pick(rng);
        if (u != v) g.addEdge(u, v);
    }
    return g;
}

int cmdRun(const std::string& path) {
    Graph g = readGraph(path);
    ArticulationFinder f(g);
    auto cuts = f.run();
    std::cout << "n=" << g.n << " m=" << g.m() << " componentes=" << f.components() << "\n";
    for (int u = 0; u < g.n; ++u)
        std::cout << "  v" << u << ": tin=" << f.tin()[u] << " low=" << f.low()[u] << " padre=" << f.parent()[u] << "\n";
    std::cout << "Articulaciones (" << cuts.size() << "):";
    for (int c : cuts) std::cout << ' ' << c;
    std::cout << "\n";
    auto brute = articulationBruteForce(g);
    std::cout << "Fuerza bruta coincide: " << (brute == cuts ? "SI" : "NO") << "\n";
    return brute == cuts ? 0 : 1;
}

int cmdTrace(const std::string& in, const std::string& out) {
    Graph g = readGraph(in);
    TraceWriter tw;
    ArticulationFinder f(g, &tw);
    auto cuts = f.run();
    if (articulationBruteForce(g) != cuts) {
        std::cerr << "ERROR: el resultado no coincide con la fuerza bruta\n";
        return 1;
    }
    std::ofstream os(out);
    writeTraceJson(g, f, cuts, tw, os);
    std::cout << in << " -> " << out << " (" << tw.size() << " eventos, " << cuts.size() << " articulaciones)\n";
    return 0;
}

int cmdTest(int cases) {
    std::mt19937 rng(2023);
    int ok = 0;
    // Casos borde deterministas.
    std::vector<Graph> fixed;
    fixed.emplace_back(0);                                      // grafo vacío
    fixed.emplace_back(1);                                      // un solo vértice
    { Graph g(2); g.addEdge(0, 1); fixed.push_back(g); }        // una arista
    { Graph g(3); g.addEdge(0, 1); g.addEdge(1, 2); fixed.push_back(g); }                // camino: 1 es corte
    { Graph g(3); g.addEdge(0, 1); g.addEdge(1, 2); g.addEdge(2, 0); fixed.push_back(g); } // ciclo: ninguno
    { Graph g(4); g.addEdge(0, 1); g.addEdge(0, 2); g.addEdge(0, 3); fixed.push_back(g); } // estrella: raíz
    { Graph g(3); g.addEdge(0, 1); g.addEdge(0, 1); g.addEdge(1, 2); fixed.push_back(g); } // arista paralela
    { Graph g(3); g.addEdge(0, 0); g.addEdge(0, 1); g.addEdge(1, 2); fixed.push_back(g); } // lazo
    for (auto& g : fixed) {
        ArticulationFinder f(g);
        if (f.run() == articulationBruteForce(g)) ++ok;
        else std::cout << "FALLO en caso fijo con n=" << g.n << "\n";
    }
    for (int t = 0; t < cases; ++t) {
        int n = std::uniform_int_distribution<int>(1, 14)(rng);
        int extra = std::uniform_int_distribution<int>(0, 2 * n)(rng);
        bool conn = std::uniform_int_distribution<int>(0, 1)(rng);
        Graph g = randomGraph(n, extra, conn, rng);
        ArticulationFinder f(g);
        if (f.run() == articulationBruteForce(g)) ++ok;
        else std::cout << "FALLO en caso aleatorio " << t << "\n";
    }
    int total = cases + static_cast<int>(fixed.size());
    std::cout << "Pruebas correctas: " << ok << " / " << total << "\n";
    return ok == total ? 0 : 1;
}

int cmdBench(const std::string& out) {
    std::mt19937 rng(7);
    std::ofstream os(out);
    os << "algoritmo,n,m,ms\n";
    auto timeIt = [](auto&& fn, int reps) {
        double best = 1e18;
        for (int r = 0; r < reps; ++r) {
            auto t0 = std::chrono::steady_clock::now();
            fn();
            auto t1 = std::chrono::steady_clock::now();
            best = std::min(best, std::chrono::duration<double, std::milli>(t1 - t0).count());
        }
        return best;
    };
    // m ≈ 3n en todos los casos (árbol aleatorio + 2n aristas extra).
    for (int n : {1000, 2000, 4000, 8000, 16000, 32000, 64000, 128000, 256000, 512000, 1000000}) {
        Graph g = randomGraph(n, 2 * n, true, rng);
        double ms = timeIt([&] { ArticulationFinder f(g); volatile auto c = f.run().size(); (void)c; }, 5);
        os << "tarjan," << n << "," << g.m() << "," << ms << "\n";
        std::cout << "tarjan n=" << n << " m=" << g.m() << " " << ms << " ms\n";
    }
    for (int n : {250, 500, 1000, 2000, 4000}) {
        Graph g = randomGraph(n, 2 * n, true, rng);
        double ms = timeIt([&] { volatile auto c = articulationBruteForce(g).size(); (void)c; }, 3);
        os << "fuerza_bruta," << n << "," << g.m() << "," << ms << "\n";
        std::cout << "fuerza_bruta n=" << n << " m=" << g.m() << " " << ms << " ms\n";
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        std::string cmd = argc > 1 ? argv[1] : "";
        if (cmd == "run" && argc == 3) return cmdRun(argv[2]);
        if (cmd == "trace" && argc == 4) return cmdTrace(argv[2], argv[3]);
        if (cmd == "test") return cmdTest(argc > 2 ? std::stoi(argv[2]) : 5000);
        if (cmd == "bench" && argc == 3) return cmdBench(argv[2]);
        std::cerr << "Uso:\n  ap run <grafo.txt>\n  ap trace <grafo.txt> <salida.json>\n"
                     "  ap test [casos]\n  ap bench <salida.csv>\n";
        return 2;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }
}
