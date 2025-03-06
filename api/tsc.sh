#!/bin/bash

# Check if TypeScript is installed globally, if not install it
if ! command -v tsc &> /dev/null; then
    echo "TypeScript not found, installing..."
    npm install -g typescript
fi

# If --watch or -w flag is passed, run in watch mode
if [[ "$1" == "--watch" ]] || [[ "$1" == "-w" ]]; then
    echo "Running TypeScript compiler in watch mode..."
    tsc -w
else
    echo "Running TypeScript compiler..."
    tsc
fi 