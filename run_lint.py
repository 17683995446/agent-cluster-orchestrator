#!/usr/bin/env python3
"""
Ruff code quality checker for Agent Cluster Orchestrator.
This script runs Ruff linting on the codebase.
"""
import subprocess
import sys
from pathlib import Path

def main():
    backend_path = Path(__file__).parent / "backend"
    
    print("🔍 Running Ruff linting on backend code...")
    
    result = subprocess.run(
        ["ruff", "check", str(backend_path)],
        capture_output=True,
        text=True
    )
    
    if result.stdout:
        print(result.stdout)
    
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    if result.returncode != 0:
        print(f"\n❌ Ruff found {len(result.stdout.splitlines())} issue(s)")
        sys.exit(1)
    else:
        print("✅ No linting issues found!")
        return 0
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
