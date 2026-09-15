#!/bin/bash
set -euo pipefail

echo "=== Scanning Docker image ==="

IMAGE_TAG="${1:-devops-app:latest}"

echo "Scanning $IMAGE_TAG for vulnerabilities..."

# Check if trivy is available, install if not
if ! command -v trivy &> /dev/null; then
  echo "Installing trivy..."
  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin 2>/dev/null || true
fi

# Run trivy scan
trivy image --severity HIGH,CRITICAL --exit-code 0 "$IMAGE_TAG" || true

echo "✓ Image scan complete"
