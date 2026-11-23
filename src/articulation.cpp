// articulation.cpp
#include "articulation.hpp"

#include <algorithm>

ArticulationFinder::ArticulationFinder(const Graph& g, TraceWriter* trace)
    : g_(g), trace_(trace), tin_(g.n, -1), low_(g.n, -1), parent_(g.n, -1), isCut_(g.n, 0) {}

std::vector<int> ArticulationFinder::run() {
    for (int s = 0; s < g_.n; ++s) {
        if (tin_[s] == -1) {
            ++components_;
            dfsFrom(s);
        }
    }
    std::vector<int> cuts;
    for (int u = 0; u < g_.n; ++u)
        if (isCut_[u]) cuts.push_back(u);
    if (trace_) {
        trace_->push(TraceWriter::Event("done").arr("cuts", cuts).num("components", components_));
    }
    return cuts;
}

// DFS iterativo (pila explícita) equivalente al recursivo:
//
//   dfs(u, pe):                       // pe = id de la arista por la que llegué
//     tin[u] = low[u] = timer++
//     for (v, id) in adj[u]:
//       if id == pe: continue         // no volver por la misma arista
//       if visitado(v): low[u] = min(low[u], tin[v])        // arista de retroceso
//       else:
//         dfs(v, id); low[u] = min(low[u], low[v])           // arista de árbol
//         if u != raíz and low[v] >= tin[u]: u es articulación
//         hijos[u]++
//   raíz es articulación  <=>  hijos[raíz] >= 2
//
// Se usa una pila explícita para no desbordar la pila de llamadas en grafos
// grandes (p. ej. un camino de 10^6 vértices).
void ArticulationFinder::dfsFrom(int root) {
    struct Frame {
        int u;      // vértice actual
        int pe;     // id de la arista padre (-1 en la raíz)
        size_t it;  // siguiente posición de adj[u] por revisar
    };
    std::vector<Frame> st;
    int rootChildren = 0;

    auto visit = [&](int u, int p, int pe) {
        tin_[u] = low_[u] = timer_++;
        parent_[u] = p;
        st.push_back({u, pe, 0});
        if (trace_)
            trace_->push(TraceWriter::Event("visit").num("u", u).num("parent", p).num("tin", tin_[u]).num("low", low_[u]));
    };

    if (trace_) trace_->push(TraceWriter::Event("start").num("root", root).num("component", components_));
    visit(root, -1, -1);

    while (!st.empty()) {
        // Copiamos los campos: un push_back posterior puede invalidar referencias.
        const int u = st.back().u;
        const int pe = st.back().pe;

        if (st.back().it < g_.adj[u].size()) {
            const auto [v, id] = g_.adj[u][st.back().it++];
            if (id == pe) {
                if (trace_) trace_->push(TraceWriter::Event("skip_parent").num("u", u).num("v", v).num("edge", id));
                continue;
            }
            if (tin_[v] == -1) {
                // Arista de árbol: descendemos.
                if (u == root) ++rootChildren;
                if (trace_) trace_->push(TraceWriter::Event("tree_edge").num("u", u).num("v", v).num("edge", id));
                visit(v, u, id);
            } else if (tin_[v] < tin_[u]) {
                // Arista de retroceso hacia un ancestro: puede bajar low[u].
                const int before = low_[u];
                low_[u] = std::min(low_[u], tin_[v]);
                if (trace_)
                    trace_->push(TraceWriter::Event("back_edge").num("u", u).num("v", v).num("edge", id)
                                     .num("tin_v", tin_[v]).num("low_before", before).num("low_after", low_[u]));
            } else {
                // tin[v] > tin[u]: v es un descendiente ya terminado; esta arista ya se
                // procesó como arista de retroceso desde v. No aporta nada nuevo.
                if (trace_) trace_->push(TraceWriter::Event("seen_descendant").num("u", u).num("v", v).num("edge", id));
            }
            continue;
        }

        // Terminamos u: retrocedemos al padre y propagamos low.
        st.pop_back();
        if (trace_) trace_->push(TraceWriter::Event("finish").num("u", u).num("tin", tin_[u]).num("low", low_[u]));
        if (st.empty()) break;

        const int p = st.back().u;
        const int before = low_[p];
        low_[p] = std::min(low_[p], low_[u]);
        const bool condition = (p != root) && (low_[u] >= tin_[p]);
        if (trace_)
            trace_->push(TraceWriter::Event("return").num("child", u).num("u", p)
                             .num("low_child", low_[u]).num("tin_u", tin_[p])
                             .num("low_before", before).num("low_after", low_[p])
                             .boolean("is_root", p == root).boolean("condition", condition));
        if (condition) {
            const bool first = !isCut_[p];
            isCut_[p] = 1;
            if (trace_)
                trace_->push(TraceWriter::Event("mark_cut").num("u", p).num("child", u)
                                 .str("rule", "low[v] >= tin[u]").boolean("first", first));
        }
    }

    const bool rootCut = rootChildren >= 2;
    if (rootCut) isCut_[root] = 1;
    if (trace_) {
        trace_->push(TraceWriter::Event("root_check").num("root", root).num("children", rootChildren).boolean("is_cut", rootCut));
        if (rootCut)
            trace_->push(TraceWriter::Event("mark_cut").num("u", root).num("child", -1).str("rule", "root has >= 2 children").boolean("first", true));
    }
}

// ---------------------------------------------------------------------------
// Fuerza bruta (solo para pruebas y comparación empírica).

int countComponents(const Graph& g, int removed) {
    std::vector<char> seen(g.n, 0);
    std::vector<int> stack;
    int comps = 0;
    for (int s = 0; s < g.n; ++s) {
        if (s == removed || seen[s]) continue;
        ++comps;
        seen[s] = 1;
        stack.push_back(s);
        while (!stack.empty()) {
            int u = stack.back();
            stack.pop_back();
            for (auto [v, id] : g.adj[u]) {
                (void)id;
                if (v != removed && !seen[v]) {
                    seen[v] = 1;
                    stack.push_back(v);
                }
            }
        }
    }
    return comps;
}

std::vector<int> articulationBruteForce(const Graph& g) {
    const int base = countComponents(g);
    std::vector<int> cuts;
    for (int v = 0; v < g.n; ++v)
        if (countComponents(g, v) > base) cuts.push_back(v);
    return cuts;
}
