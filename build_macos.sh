#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-build.txt
pyinstaller --clean --noconfirm xhs_package_generator.spec

echo "Build complete: dist/XHS_Package_Generator"
