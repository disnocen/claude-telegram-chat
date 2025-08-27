#!/bin/bash
# Custom build script for Vercel to use uv

echo "Installing uv..."
pip install uv

echo "Installing dependencies with uv..."
uv pip install --system -r requirements.txt

echo "Dependencies installed successfully!"