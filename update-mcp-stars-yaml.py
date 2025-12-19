#!/usr/bin/env python3
"""
Update GitHub star counts for all MCP servers in a YAML manifest file.

Usage:
    # With GitHub token (recommended - 5000 requests/hour):
    GITHUB_TOKEN=your_token python3 scripts/update-mcp-stars-yaml.py path/to/manifest.yaml

    # Without token (limited to 60 requests/hour):
    python3 scripts/update-mcp-stars-yaml.py path/to/manifest.yaml

Requirements:
    pip install requests ruamel.yaml
"""

import os
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: 'requests' package not found. Install with: pip install requests")
    sys.exit(1)

try:
    from ruamel.yaml import YAML
except ImportError:
    print("Error: 'ruamel.yaml' package not found. Install with: pip install ruamel.yaml")
    sys.exit(1)

GITHUB_API = "https://api.github.com"


def extract_repo_info(github_url: str) -> tuple[str, str] | None:
    """Extract owner and repo from various GitHub URL formats."""
    if not github_url:
        return None
    
    # Match patterns like:
    # - https://github.com/owner/repo
    # - https://github.com/owner/repo/tree/main/path
    # - github.com/owner/repo
    patterns = [
        r"github\.com/([^/]+)/([^/]+?)(?:/tree/|/blob/|$|\.git)",
        r"github\.com/([^/]+)/([^/]+)$",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, github_url)
        if match:
            owner = match.group(1)
            repo = match.group(2).rstrip("/")
            return owner, repo
    
    return None


def get_star_count(owner: str, repo: str, headers: dict) -> int | None:
    """Fetch star count for a GitHub repository."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("stargazers_count", 0)
        elif response.status_code == 404:
            print(f"  ⚠ Repository not found: {owner}/{repo}")
            return None
        elif response.status_code == 403:
            # Rate limited
            reset_time = response.headers.get("X-RateLimit-Reset")
            if reset_time:
                wait_seconds = int(reset_time) - int(time.time())
                print(f"  ⚠ Rate limited. Resets in {wait_seconds}s")
            return None
        else:
            print(f"  ⚠ Error {response.status_code} for {owner}/{repo}")
            return None
            
    except requests.RequestException as e:
        print(f"  ⚠ Request failed for {owner}/{repo}: {e}")
        return None


def check_rate_limit(headers: dict) -> tuple[int, int]:
    """Check current rate limit status."""
    url = f"{GITHUB_API}/rate_limit"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            remaining = data["rate"]["remaining"]
            limit = data["rate"]["limit"]
            return remaining, limit
    except:
        pass
    return -1, -1


def main():
    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: update-mcp-stars-yaml.py <path/to/manifest.yaml>")
        print("Example: update-mcp-stars-yaml.py ../pkg/flowstore/data/taps/official.yaml")
        sys.exit(1)
    
    yaml_file = Path(sys.argv[1])
    
    if not yaml_file.exists():
        print(f"Error: YAML file not found: {yaml_file}")
        sys.exit(1)
    
    # Check for GitHub token
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "astonish-mcp-store-updater"
    }
    
    if token:
        headers["Authorization"] = f"token {token}"
        print("✓ Using GitHub token (5000 requests/hour limit)")
    else:
        print("⚠ No GITHUB_TOKEN found - using unauthenticated access (60 requests/hour limit)")
        print("  Set GITHUB_TOKEN environment variable for higher limits")
    
    # Check rate limit
    remaining, limit = check_rate_limit(headers)
    if remaining >= 0:
        print(f"  Rate limit: {remaining}/{limit} remaining")
    
    # Load YAML file using ruamel.yaml to preserve formatting
    print(f"\nLoading: {yaml_file}")
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # Prevent line wrapping
    
    with open(yaml_file, "r") as f:
        data = yaml.load(f)
    
    # Find the mcps section
    if "mcps" not in data:
        print("Error: No 'mcps' section found in YAML file")
        sys.exit(1)
    
    mcps = data["mcps"]
    mcp_count = len(mcps)
    print(f"Found {mcp_count} MCP servers to update...")
    print("-" * 50)
    
    updated = 0
    failed = 0
    unchanged = 0
    
    # mcps is a dict where key is the mcp name, value is the config
    for i, (name, mcp) in enumerate(mcps.items()):
        # Handle case where mcp might just be a string or None
        if not isinstance(mcp, dict):
            print(f"[{i+1}/{mcp_count}] {name}: ⚠ Invalid config format")
            failed += 1
            continue
            
        github_url = mcp.get("githubUrl", "")
        old_stars = mcp.get("githubStars", 0) or 0
        
        repo_info = extract_repo_info(github_url)
        if not repo_info:
            print(f"[{i+1}/{mcp_count}] {name}: ⚠ Could not parse GitHub URL")
            failed += 1
            continue
        
        owner, repo = repo_info
        new_stars = get_star_count(owner, repo, headers)
        
        if new_stars is None:
            failed += 1
            continue
        
        if new_stars != old_stars:
            diff = new_stars - old_stars
            diff_str = f"+{diff}" if diff > 0 else str(diff)
            print(f"[{i+1}/{mcp_count}] {name}: {old_stars} → {new_stars} ({diff_str})")
            mcp["githubStars"] = new_stars
            updated += 1
        else:
            print(f"[{i+1}/{mcp_count}] {name}: {new_stars} (unchanged)")
            unchanged += 1
        
        # Small delay to be nice to the API
        time.sleep(0.1)
    
    print("-" * 50)
    print(f"Summary: {updated} updated, {unchanged} unchanged, {failed} failed")
    
    # Save updated YAML file (ruamel.yaml preserves formatting)
    if updated > 0:
        with open(yaml_file, "w") as f:
            yaml.dump(data, f)
        print(f"\n✓ Saved updated star counts to {yaml_file}")
    else:
        print("\nNo changes to save.")


if __name__ == "__main__":
    main()
