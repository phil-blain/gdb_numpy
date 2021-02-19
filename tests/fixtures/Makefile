CXX = g++
CXXFLAGS = -g -O0

APP=TestCppArray

.PHONY: clean

$(APP): ../$(APP).cpp
	$(CXX) $(CXXFLAGS) $< -o $@

build:
	mkdir $@

clean:
	rm -rf *.o *.dSYM $(APP)
