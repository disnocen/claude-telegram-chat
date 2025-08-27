#!/bin/bash
# Custom build script for Vercel to use uv

echo "Installing uv via official installer..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

echo "Checking uv version..."
uv --version

echo "Creating virtual environment with uv..."
uv venv

echo "Installing dependencies with uv..."
uv pip sync requirements.txt

echo "Dependencies installed successfully!"

# Copy pyproject.toml to api directory for Vercel
cp pyproject.toml api/ 2>/dev/null || true