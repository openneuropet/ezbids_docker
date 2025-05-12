#!/usr/bin/env bash
set -e

# Explicitly set working directory
cd /ui

# Explicitly install dependencies (ensure this runs)
npm install

# Explicitly start the Vite dev server explicitly on all interfaces
npm run dev -- --host 0.0.0.0
