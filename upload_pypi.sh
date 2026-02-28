#!/bin/bash
# Chou - Upload to PyPI
# Usage: ./upload_pypi.sh [--test]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Chou PyPI Upload Script ===${NC}"

# Get version from __version__.py
VERSION=$(python3 -c "from chou.__version__ import __version__; print(__version__)")
echo -e "Version: ${YELLOW}${VERSION}${NC}"

# Check for --test flag
if [ "$1" == "--test" ]; then
    REPO="testpypi"
    REPO_URL="https://test.pypi.org/legacy/"
    echo -e "${YELLOW}Uploading to TestPyPI${NC}"
else
    REPO="pypi"
    REPO_URL=""
    echo -e "${YELLOW}Uploading to PyPI${NC}"
fi

# Clean previous builds
echo -e "${GREEN}Cleaning previous builds...${NC}"
rm -rf dist/ build/ *.egg-info chou.egg-info

# Build the package
echo -e "${GREEN}Building package...${NC}"
python3 -m pip install --upgrade build twine -q
python3 -m build

# Check the distribution
echo -e "${GREEN}Checking distribution...${NC}"
python3 -m twine check dist/*

# Upload to PyPI
echo -e "${GREEN}Uploading to ${REPO}...${NC}"
if [ "$REPO" == "testpypi" ]; then
    python3 -m twine upload --repository testpypi dist/*
else
    python3 -m twine upload dist/*
fi

echo -e "${GREEN}Done! Chou v${VERSION} uploaded to ${REPO}${NC}"
echo -e "Install with: ${YELLOW}pip install chou${NC}"
