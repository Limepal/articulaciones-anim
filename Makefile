CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -pedantic
PYTHON   ?= python3

SRC  = src/main.cpp src/articulation.cpp
BIN  = build/ap
DATA = $(wildcard data/*.txt)
TRACES = $(patsubst data/%.txt,out/traces/%.json,$(DATA))

.PHONY: all test traces bench video stills clean

all: $(BIN)

$(BIN): $(SRC) src/*.hpp
	@mkdir -p build
	$(CXX) $(CXXFLAGS) $(SRC) -o $@

test: $(BIN)
	./$(BIN) test 5000

out/traces/%.json: data/%.txt $(BIN)
	@mkdir -p out/traces
	./$(BIN) trace $< $@

traces: $(TRACES)

bench: $(BIN)
	@mkdir -p out
	./$(BIN) bench out/bench.csv

video: traces out/bench.csv
	$(PYTHON) anim/render.py --traces out/traces --bench out/bench.csv --out out/articulaciones.mp4

stills: traces out/bench.csv
	$(PYTHON) anim/render.py --traces out/traces --bench out/bench.csv --stills-only --stills-dir out/figuras

out/bench.csv: $(BIN)
	@mkdir -p out
	./$(BIN) bench out/bench.csv

clean:
	rm -rf build out
