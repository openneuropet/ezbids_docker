#!/usr/bin/env bash

cd ..
cd handler/
pm2 start handler.js --attach --watch --ignore-watch "ui **/node_modules"
