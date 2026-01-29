#!/bin/bash
# Migrate Python Agent from backend/agent/ to top-level agent/
# Run from project root: bash scripts/migrate-agent.sh

set -e

echo "=== Migrating Python Agent ==="

SRC="backend/agent"
DEST="agent"

# Copy files (skip main.py since we already created the updated version)
echo "Copying core files..."
for f in args.py model.py hook.py tool_registry.py __init__.py; do
    if [ -f "$SRC/$f" ]; then
        cp "$SRC/$f" "$DEST/$f"
        echo "  Copied $f"
    fi
done

# Copy subdirectories
for dir in plan tool utils; do
    if [ -d "$SRC/$dir" ]; then
        cp -r "$SRC/$dir" "$DEST/$dir"
        echo "  Copied $dir/"
    fi
done

# Migrate prompts to top-level
if [ -d "backend/prompts" ]; then
    if [ ! -d "prompts" ]; then
        mkdir -p prompts
    fi
    cp -r backend/prompts/* prompts/ 2>/dev/null || true
    echo "  Copied prompts/"
fi

echo ""
echo "=== Migration Complete ==="
echo "Files in agent/:"
ls -la agent/
echo ""
echo "Next steps:"
echo "  1. Verify: cd agent && python main.py --help"
echo "  2. Test agent spawn from Node.js server"
