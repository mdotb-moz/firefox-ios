import os
import requests
import re

# Define constants
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Navigate one level up from "test"
BITRISE_YML = os.path.join(BASE_DIR, "bitrise.yml")
BITRISE_STEPLIB_URL = "https://api.github.com/repos/bitrise-io/bitrise-steplib/contents/steps"

# GitHub Access Token
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Step versions that should NOT be updated
"""
We need to lock this version because the new version of git-clone step brokes the decision 
to run UI test step due to the change in the variables available. Once we investigate this
failure in the workflow, eventually we can remove the locked version.
"""
LOCKED_VERSIONS = {
    "git-clone": "6.2"
}

"""
We need to skip some workflows because updating the steps cause some failure and break the workflow
"""
# Workflows to skip completely
SKIPPED_WORKFLOWS = {
    "focus_SPM_Nightly"
}

def fetch_latest_version(step_id):
    """Fetch the latest version of a step from the Bitrise Step Library."""
    if step_id in LOCKED_VERSIONS:
        print(f"Skipping update for {step_id}, keeping version {LOCKED_VERSIONS[step_id]}")
        return LOCKED_VERSIONS[step_id]  # Return locked version

    try:
        url = f"{BITRISE_STEPLIB_URL}/{step_id}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        items = response.json()
        # Filter out directories that represent versions
        versions = [
            item["name"] for item in items
            if all(c.isdigit() or c == '.' for c in item["name"])
        ]
        if not versions:
            print(f"No valid versions found for step {step_id}.")
            return None
        latest_version = sorted(versions, key=lambda x: list(map(int, x.split('.'))))[-1]
        return latest_version
    except requests.exceptions.RequestException as e:
        print(f"Error fetching latest version for {step_id}: {e}")
        return None

def update_bitrise_yaml():
    """Update outdated steps in the Bitrise YAML file, except locked workflows."""
    with open(BITRISE_YML, "r") as file:
        content = file.readlines()

    updated_lines = []
    updated_steps = []
    skip_workflow = False  # Track if we are inside a skipped workflow
    inside_skipped_steps = False  # Track if we are inside `steps:` under a skipped workflow

    for line in content:
        # Detect workflow names and determine if they should be skipped
        workflow_match = re.match(r"^\s*([a-zA-Z0-9\-_]+):\s*$", line)
        if workflow_match:
            workflow_name = workflow_match.group(1)
            skip_workflow = workflow_name in SKIPPED_WORKFLOWS
            inside_skipped_steps = False  # Reset when a new workflow starts

            if skip_workflow:
                print(f"Skipping entire workflow: {workflow_name}")

        # Detect `steps:` inside a skipped workflow and ensure we skip everything after
        if skip_workflow and re.match(r"^\s*steps:\s*$", line):
            inside_skipped_steps = True  # Now we are inside steps and should skip all below

        # Skip all lines inside a skipped workflow's `steps:` section
        if skip_workflow and inside_skipped_steps:
            updated_lines.append(line)
            continue

        # Match step lines and update only if we are NOT inside a skipped workflow
        match = re.match(r"^\s*-\s*([a-zA-Z0-9\-_]+)@([\d\.]+):", line)
        if match and not skip_workflow:  # ✅ Ensure we do NOT update steps in skipped workflows
            step_id, current_version = match.groups()
            latest_version = fetch_latest_version(step_id)
            if latest_version and current_version != latest_version:
                updated_steps.append(f"{step_id}: {current_version} -> {latest_version}")
                line = line.replace(f"{step_id}@{current_version}", f"{step_id}@{latest_version}")

        updated_lines.append(line)

    # Write back the updated file
    with open(BITRISE_YML, "w") as file:
        file.writelines(updated_lines)

    if updated_steps:
        print("Updated steps:")
        print("\n".join(updated_steps))
    else:
        print("No updates were necessary.")
        
if __name__ == "__main__":
    update_bitrise_yaml()
