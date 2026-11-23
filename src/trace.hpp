// trace.hpp
// Registro de eventos del algoritmo. El algoritmo NO sabe nada de animación:
// solo avisa "visité u", "encontré una arista de retroceso", etc. Esta clase
// guarda esos eventos y los serializa a JSON. El renderizador en Python lee
// ese JSON y dibuja exactamente lo que ocurrió (animación "real").
#pragma once
#include <ostream>
#include <sstream>
#include <string>
#include <vector>

class TraceWriter {
public:
    // Construye un evento como lista de pares clave:valor ya formateados.
    class Event {
    public:
        explicit Event(std::string type) { kv_.push_back("\"type\":\"" + type + "\""); }
        Event& num(const std::string& k, long long v) {
            kv_.push_back("\"" + k + "\":" + std::to_string(v));
            return *this;
        }
        Event& boolean(const std::string& k, bool v) {
            kv_.push_back("\"" + k + "\":" + (v ? "true" : "false"));
            return *this;
        }
        Event& str(const std::string& k, const std::string& v) {
            kv_.push_back("\"" + k + "\":\"" + escape(v) + "\"");
            return *this;
        }
        Event& arr(const std::string& k, const std::vector<int>& v) {
            std::ostringstream os;
            os << "\"" << k << "\":[";
            for (size_t i = 0; i < v.size(); ++i) os << (i ? "," : "") << v[i];
            os << "]";
            kv_.push_back(os.str());
            return *this;
        }
        std::string json() const {
            std::string s = "{";
            for (size_t i = 0; i < kv_.size(); ++i) s += (i ? "," : "") + kv_[i];
            return s + "}";
        }
    private:
        static std::string escape(const std::string& s) {
            std::string r;
            for (char c : s) {
                if (c == '"' || c == '\\') r += '\\';
                r += c;
            }
            return r;
        }
        std::vector<std::string> kv_;
    };

    void push(const Event& e) { events_.push_back(e.json()); }
    size_t size() const { return events_.size(); }

    void writeArray(std::ostream& os) const {
        os << "[\n";
        for (size_t i = 0; i < events_.size(); ++i)
            os << "  " << events_[i] << (i + 1 < events_.size() ? ",\n" : "\n");
        os << "]";
    }

private:
    std::vector<std::string> events_;
};
