#!/bin/bash
set -euo pipefail

echo "=== Restore Test: Round-Trip Data Verification ==="
echo "Started at: $(date)"

# Configuration
RESTIC_REPO="${RESTIC_REPO:-/mnt/backups/restic-repo}"
RESTIC_PASSWORD="${RESTIC_PASSWORD:-devops-backup-password}"
APP_PVC_NAME="${APP_PVC_NAME:-devops-app-data}"
APP_NAMESPACE="${APP_NAMESPACE:-devops}"
TEMP_DIR="${TEMP_DIR:-/tmp/restore-test}"

export RESTIC_REPOSITORY="$RESTIC_REPO"
export RESTIC_PASSWORD="$RESTIC_PASSWORD"

# Step 1: Write test data
echo ""
echo "Step 1: Writing test data to the app..."
for i in {1..5}; do
  curl -s -X POST http://localhost:8080/items \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"test-item-$i\",\"description\":\"Restore test item $i\"}" \
    || echo "Warning: Could not create item $i (app may not be ready)"
done

# Step 2: Backup the data directory
echo ""
echo "Step 2: Creating backup..."
restic backup /app \
  --tag "restore-test" \
  --exclude '*.pyc' \
  --exclude '__pycache__'

# Get the latest snapshot ID
SNAPSHOT_ID=$(restic snapshots --json | jq -r '.[-1].id')
echo "Latest snapshot: $SNAPSHOT_ID"

# Step 3: Calculate checksum of original data
echo ""
echo "Step 3: Calculating original data checksum..."
ORIGINAL_CHECKSUM=$(tar czf - /app/app.db 2>/dev/null | sha256sum | awk '{print $1}')
echo "Original checksum: $ORIGINAL_CHECKSUM"
echo "$ORIGINAL_CHECKSUM" > /tmp/original.checksum

# Step 4: Wipe the data (simulate disaster)
echo ""
echo "Step 4: Deleting application data (simulating data loss)..."
rm -f /app/app.db
echo "✓ Data deleted"

# Step 5: Restore from backup
echo ""
echo "Step 5: Restoring from backup snapshot $SNAPSHOT_ID..."
mkdir -p "$TEMP_DIR"
restic restore "$SNAPSHOT_ID" --target "$TEMP_DIR"

# Step 6: Verify checksums match
echo ""
echo "Step 6: Verifying restore integrity..."
RESTORED_CHECKSUM=$(tar czf - "$TEMP_DIR/app/app.db" 2>/dev/null | sha256sum | awk '{print $1}')
echo "Restored checksum: $RESTORED_CHECKSUM"

if [ "$ORIGINAL_CHECKSUM" == "$RESTORED_CHECKSUM" ]; then
  echo "✓ CHECKSUMS MATCH - Restore successful!"
else
  echo "✗ CHECKSUMS DO NOT MATCH - Restore failed!"
  exit 1
fi

# Step 7: Copy restored data back to original location
echo ""
echo "Step 7: Restoring data to original location..."
cp "$TEMP_DIR/app/app.db" /app/app.db
chmod 644 /app/app.db

# Step 8: Verify app can query the restored data
echo ""
echo "Step 8: Verifying app can access restored data..."
sleep 2
ITEM_COUNT=$(curl -s http://localhost:8080/items | jq 'length' 2>/dev/null || echo "0")
echo "Items in restored database: $ITEM_COUNT"

if [ "$ITEM_COUNT" -ge 5 ]; then
  echo "✓ Data verification passed - all items restored"
else
  echo "⚠ Warning: Expected ≥5 items, found $ITEM_COUNT"
fi

# Cleanup
echo ""
echo "Step 9: Cleaning up temporary files..."
rm -rf "$TEMP_DIR"
rm -f /tmp/original.checksum

echo ""
echo "=== Restore Test Completed Successfully ==="
echo "Completed at: $(date)"
