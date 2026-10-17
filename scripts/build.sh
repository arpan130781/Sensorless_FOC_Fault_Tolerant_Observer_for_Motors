#!/bin/bash
set -e

OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
    LIB_EXT="dylib"
else
    LIB_EXT="so"
fi

BUILD_DIR="build"
SRC_DIR="src"
mkdir -p "$BUILD_DIR"

echo "Compiling controller library..."
gcc -Wall -Wextra -O2 -fPIC -shared -lm $(find "$SRC_DIR" -maxdepth 1 -name "*.c") -o "$BUILD_DIR/libfoc_controller.$LIB_EXT"

echo "Success! Library built at $BUILD_DIR/libfoc_controller.$LIB_EXT"
