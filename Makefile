PYTHON ?= $(shell if [ -x .venv/bin/python3 ]; then echo .venv/bin/python3; else which python3; fi)

CC=gcc
CFLAGS=-Wall -Wextra -O2 -fPIC
SRC_DIR=src
BUILD_DIR=build
SCENARIO ?= scenario_0_no_fault

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
	LIB_EXT := dylib
else
	LIB_EXT := so
endif

LIB_TARGET := $(BUILD_DIR)/libfoc_controller.$(LIB_EXT)
SRCS := $(filter-out $(SRC_DIR)/tests/%, $(wildcard $(SRC_DIR)/*.c))

.PHONY: all lib test pytest test-all clean run run-scenario

all: lib

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

lib: $(BUILD_DIR)
	$(CC) $(CFLAGS) -shared $(SRCS) -lm -o $(LIB_TARGET)

test: lib
	$(CC) $(CFLAGS) $(SRC_DIR)/tests/test_transforms.c $(SRCS) -lm -o $(BUILD_DIR)/test_transforms
	./$(BUILD_DIR)/test_transforms

pytest:
	$(PYTHON) -m pytest simulation/ -v

test-all: test pytest

clean:
	rm -rf $(BUILD_DIR)

run: lib
	$(PYTHON) simulation/harness/sil_runner.py

run-scenario: lib
	$(PYTHON) simulation/harness/sil_runner.py --scenario $(SCENARIO)
