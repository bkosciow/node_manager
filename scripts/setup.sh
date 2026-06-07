#!/bin/bash
set -e

echo "Setting up IoT Device Discovery Service..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker not found. Please install Docker first."
    exit 1
fi

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose not found. Please install Docker Compose v2."
    exit 1
fi

# Copy environment file
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please edit .env with your configuration."
fi

# Start services
echo "Starting Docker services..."
docker compose up -d --build

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your configuration"
echo "  2. Open http://localhost:9092/docs for API documentation"
echo "  3. Run 'make test' to verify the setup"
echo ""
echo "Useful commands:"
echo "  make dev       - Start development"
echo "  make test      - Run tests"
echo "  make prod-up   - Start production"
echo "  make help      - Show all commands"
