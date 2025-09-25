#!/bin/bash

# Lab 02 Test Script - Container Stop Functionality
# This script demonstrates various stop commands and scenarios

echo "=== Lab 02: Container Stop Testing ==="
echo

# Ensure we're using the proper host (adjust as needed)
export DOCKYARD_HOST=${DOCKYARD_HOST:-localhost}

echo "1. Launch test containers..."
python3 cli/main.py launch nginx:alpine --name web-server
python3 cli/main.py launch redis:alpine --name cache
python3 cli/main.py launch -f labs/lab2-stop/app.yaml

echo
echo "2. Basic stop command..."
python3 cli/main.py stop web-server

echo
echo "3. Stop multiple containers..."
python3 cli/main.py stop cache nginx-app

echo
echo "4. Force stop demo (launch new container first)..."
python3 cli/main.py launch busybox:latest --name test-force
sleep 2
python3 cli/main.py stop --force test-force

echo
echo "5. Stop with custom timeout..."
python3 cli/main.py launch nginx:alpine --name timeout-test
sleep 2
python3 cli/main.py stop --timeout 30 timeout-test

echo
echo "6. Error cases..."
echo "6a. Stop non-existent container:"
python3 cli/main.py stop non-existent

echo
echo "6b. Stop already stopped container:"
python3 cli/main.py stop web-server

echo
echo "=== Lab 02 Testing Complete ==="