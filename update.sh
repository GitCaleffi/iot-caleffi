#!/bin/bash
# Manual update script

echo "🔄 Checking for updates..."
cd "$(dirname "$0")"

python3 src/utils/auto_updater.py --check
if [[ $? -eq 0 ]]; then
    echo "📥 Performing update..."
    python3 src/utils/auto_updater.py --update
else
    echo "✅ Already up to date"
fi
