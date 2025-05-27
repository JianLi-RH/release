#!/usr/bin/env python3
"""
Update staged CI configuration files with version bumps for release migration.

This script processes staged YAML files and updates:
- tests-private-postupg tag to "4.22"
- tests-private-preupg tag to "4.21"
- custom.candidate.version to "4.21"
- zz_generated_metadata.branch to "release-4.22"
- zz_generated_metadata.variant to amd64-nightly-4.22-upgrade-from-stable-4.xx
"""

import argparse
import subprocess
import sys
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


def staged_files():
    """Staged all changes from git."""
    try:
        result = subprocess.run(
            ["git", "add", "."],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error stage files: {e}")
        sys.exit(1)

def get_staged_files():
    """Get list of staged files from git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            capture_output=True,
            text=True,
            check=True
        )
        files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
        return files
    except subprocess.CalledProcessError as e:
        print(f"Error getting staged files: {e}")
        sys.exit(1)


def update_yaml_file(file_path, target_version, prior_version):
    """Update version fields in a YAML configuration file using line-based editing.

    Args:
        file_path: Path to the YAML file
        target_version: Target release version (e.g., "4.22")
        prior_version: Prior/source release version (e.g., "4.21")
    """
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        modified = False
        in_section = None
        indent_stack = []

        for i, line in enumerate(lines):
            # Track indentation to understand YAML structure
            stripped = line.lstrip()
            if not stripped or stripped.startswith('#'):
                continue

            indent = len(line) - len(stripped)

            # Detect sections
            if line.strip() == 'base_images:':
                in_section = 'base_images'
                indent_stack = [indent]
                continue
            elif line.strip() == 'releases:':
                in_section = 'releases'
                indent_stack = [indent]
                continue
            elif line.strip() == 'zz_generated_metadata:':
                in_section = 'zz_generated_metadata'
                indent_stack = [indent]
                continue
            elif indent <= (indent_stack[0] if indent_stack else -1) and ':' in line:
                in_section = None
                indent_stack = []

            # Update tests-private-postupg tag to target_version
            if in_section == 'base_images' and 'tests-private-postupg:' in line:
                # Look ahead for the tag field
                for j in range(i+1, min(i+5, len(lines))):
                    if re.match(r'\s+tag:\s+["\']?[\d.]+["\']?', lines[j]):
                        old_line = lines[j]
                        lines[j] = re.sub(
                            r'(tag:\s+["\']?)[\d.]+(["\']?)',
                            rf'\g<1>{target_version}\g<2>',
                            lines[j]
                        )
                        if old_line != lines[j]:
                            modified = True
                            old_val = re.search(r'tag:\s+["\']?([\d.]+)["\']?', old_line).group(1)
                            print(f"  - Updated tests-private-postupg tag: {old_val} → {target_version}")
                        break

            # Update tests-private-preupg tag to prior_version
            if in_section == 'base_images' and 'tests-private-preupg:' in line:
                # Look ahead for the tag field
                for j in range(i+1, min(i+5, len(lines))):
                    if re.match(r'\s+tag:\s+["\']?[\d.]+["\']?', lines[j]):
                        old_line = lines[j]
                        lines[j] = re.sub(
                            r'(tag:\s+["\']?)[\d.]+(["\']?)',
                            rf'\g<1>{prior_version}\g<2>',
                            lines[j]
                        )
                        if old_line != lines[j]:
                            modified = True
                            old_val = re.search(r'tag:\s+["\']?([\d.]+)["\']?', old_line).group(1)
                            print(f"  - Updated tests-private-preupg tag: {old_val} → {prior_version}")
                        break

            # Update version fields in releases section
            if in_section == 'releases' and re.match(r'\s+version:\s+["\']?[\d.]+["\']?', line):
                # Check which release section we're in by looking back
                section_type = None
                for j in range(max(0, i-5), i):
                    if 'custom:' in lines[j]:
                        section_type = 'custom'
                        break
                    elif re.match(r'^\s+target:\s*$', lines[j]):
                        section_type = 'target'
                        break
                    elif 'arm64-target:' in lines[j]:
                        section_type = 'arm64-target'
                        break

                # Update based on section type
                if section_type == 'custom':
                    # custom.candidate.version -> prior_version
                    old_line = line
                    line = re.sub(
                        r'(version:\s+["\']?)[\d.]+(["\']?)',
                        rf'\g<1>{prior_version}\g<2>',
                        line
                    )
                    if old_line != line:
                        modified = True
                        old_val = re.search(r'version:\s+["\']?([\d.]+)["\']?', old_line).group(1)
                        print(f"  - Updated custom.candidate.version: {old_val} → {prior_version}")
                        lines[i] = line
                elif section_type in ['target', 'arm64-target']:
                    # target.candidate.version or arm64-target.candidate.version -> target_version
                    old_line = line
                    line = re.sub(
                        r'(version:\s+["\']?)[\d.]+(["\']?)',
                        rf'\g<1>{target_version}\g<2>',
                        line
                    )
                    if old_line != line:
                        modified = True
                        old_val = re.search(r'version:\s+["\']?([\d.]+)["\']?', old_line).group(1)
                        print(f"  - Updated {section_type}.candidate.version: {old_val} → {target_version}")
                        lines[i] = line

            # Update zz_generated_metadata.branch
            if in_section == 'zz_generated_metadata' and re.match(r'\s+branch:\s+\S+', line):
                old_line = line
                line = re.sub(
                    r'(branch:\s+)\S+',
                    rf'\g<1>release-{target_version}',
                    line
                )
                if old_line != line:
                    modified = True
                    old_val = re.search(r'branch:\s+(\S+)', old_line).group(1)
                    print(f"  - Updated zz_generated_metadata.branch: {old_val} → release-{target_version}")
                    lines[i] = line

            # Update zz_generated_metadata.variant
            if in_section == 'zz_generated_metadata' and re.match(r'\s+variant:\s+\S+', line):
                old_line = line
                # Replace prior version with target version in the middle of the variant string
                # Pattern: amd64-nightly-4.21-upgrade-from-stable-4.xx
                # Preserves the nightly/stable part, only updates the version number
                escaped_prior = re.escape(prior_version)
                line = re.sub(
                    rf'(variant:\s+\w+-)([a-z]+-){escaped_prior}(-upgrade-from-stable-4\.\d+)',
                    rf'\g<1>\g<2>{target_version}\g<3>',
                    line
                )
                if old_line != line:
                    modified = True
                    old_val = re.search(r'variant:\s+(\S+)', old_line).group(1)
                    new_val = re.search(r'variant:\s+(\S+)', line).group(1)
                    print(f"  - Updated zz_generated_metadata.variant: {old_val} → {new_val}")
                    lines[i] = line

        # Write back if modified
        if modified:
            with open(file_path, 'w') as f:
                f.writelines(lines)
            return True

        return False

    except Exception as e:
        print(f"  Error processing file: {e}")
        import traceback
        traceback.print_exc()
        return False


def rename_chain_upgrade_configs(source_version, target_version, config_dir="ci-operator/config/openshift/openshift-tests-private", dry_run=False, exclude_automated=True):
    """Rename chain upgrade config files from source version to target version.

    Args:
        source_version: Source release version (e.g., "4.21")
        target_version: Target release version (e.g., "4.22")
        config_dir: Directory containing the config files
        dry_run: If True, only print what would be renamed without actually renaming
        exclude_automated: If True, exclude automated-release-stable configs (default: True)

    Returns:
        List of tuples (old_path, new_path) for renamed files

    Example:
        Renames files like:
        openshift-openshift-tests-private-release-4.21__amd64-nightly-4.21-upgrade-from-stable-4.16.yaml
        to:
        openshift-openshift-tests-private-release-4.22__amd64-nightly-4.22-upgrade-from-stable-4.16.yaml
    """
    import glob
    import os

    renamed_files = []

    # Pattern to match chain upgrade config files
    # Format: {org}-{repo}-release-{version}__{variant}-{version}-upgrade-from-stable-{base_version}.yaml
    pattern = f"{config_dir}/*-release-{source_version}__*-{source_version}-upgrade-from-stable-*.yaml"

    matching_files = glob.glob(pattern)

    # Filter out automated-release-stable configs if requested
    if exclude_automated:
        matching_files = [f for f in matching_files if '__automated-release-stable-' not in f]

    if not matching_files:
        print(f"No chain upgrade config files found matching pattern: {pattern}")
        return renamed_files

    print(f"\nFound {len(matching_files)} chain upgrade config file(s) to rename:\n")

    for old_path in matching_files:
        old_filename = os.path.basename(old_path)

        # Replace release-{source_version} with release-{target_version}
        new_filename = old_filename.replace(f"-release-{source_version}__", f"-release-{target_version}__")

        # Replace {source_version}-upgrade with {target_version}-upgrade
        # Use regex to be more precise and avoid replacing the "from-stable-X.XX" part
        new_filename = re.sub(
            rf'__(.+?)-{re.escape(source_version)}-upgrade-from',
            rf'__\1-{target_version}-upgrade-from',
            new_filename
        )

        new_path = os.path.join(config_dir, new_filename)

        if old_path == new_path:
            print(f"⊘ {old_filename} (no change needed)")
            continue

        print(f"→ {old_filename}")
        print(f"  ⇒ {new_filename}")

        if not dry_run:
            try:
                # Use git mv to rename the file
                subprocess.run(
                    ["git", "mv", old_path, new_path],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(f"  ✓ Renamed successfully")
                renamed_files.append((old_path, new_path))
            except subprocess.CalledProcessError as e:
                print(f"  ✗ Error renaming: {e.stderr.strip()}")
        else:
            print(f"  (dry run - not actually renamed)")
            renamed_files.append((old_path, new_path))

        print()

    return renamed_files


def main(target_version, prior_version):
    """Main function."""
    
    print("Fetching staged files...")
    staged_files = get_staged_files()

    if not staged_files:
        print("No staged files found.")
        return

    print(f"\nFound {len(staged_files)} staged file(s):\n")

    # Filter for YAML files in ci-operator/config
    yaml_files = [
        f for f in staged_files
        if f.endswith('.yaml') and f.startswith('ci-operator/config/')
    ]

    if not yaml_files:
        print("No YAML configuration files found in staged files.")
        return

    print(f"Processing {len(yaml_files)} YAML configuration file(s)...\n")

    updated_count = 0
    for file_path in yaml_files:
        if not Path(file_path).exists():
            print(f"⊘ {file_path} (file deleted)")
            continue

        print(f"→ {file_path}")
        if update_yaml_file(file_path, target_version, prior_version):
            updated_count += 1
        else:
            print(f"  - No changes needed")
        print()

    print(f"\nSummary: Updated {updated_count} of {len(yaml_files)} file(s).")

    if updated_count > 0:
        print("\nNote: Modified files are already staged. Review changes with 'git diff --staged'")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Rename chain upgrade config files from source version to target version.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (preview changes without renaming)
  %(prog)s --source 4.21 --target 4.22 --dry-run

  # Actually rename the files
  %(prog)s --source 4.21 --target 4.22

  # Specify custom config directory
  %(prog)s -s 4.21 -t 4.22 --config-dir /path/to/configs
        """
    )

    parser.add_argument(
        '-s', '--source',
        required=True,
        help='Source release version (e.g., "4.21")'
    )
    parser.add_argument(
        '-t', '--target',
        required=True,
        help='Target release version (e.g., "4.22")'
    )
    parser.add_argument(
        '--config-dir',
        default='ci-operator/config/openshift/openshift-tests-private',
        help='Directory containing config files (default: ci-operator/config/openshift/openshift-tests-private)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be renamed without actually renaming'
    )
    parser.add_argument(
        '--include-automated',
        action='store_true',
        help='Include automated-release-stable configs in rename (default: excluded)'
    )

    args = parser.parse_args()

    print(f"Chain Upgrade Config Renamer")
    print(f"=" * 50)
    print(f"Source version: {args.source}")
    print(f"Target version: {args.target}")
    print(f"Config directory: {args.config_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'RENAME'}")
    print(f"Automated configs: {'INCLUDED' if args.include_automated else 'EXCLUDED'}")
    print(f"=" * 50)

    renamed = rename_chain_upgrade_configs(
        args.source,
        args.target,
        config_dir=args.config_dir,
        dry_run=args.dry_run,
        exclude_automated=not args.include_automated
    )

    if renamed:
        print(f"\n{'Would rename' if args.dry_run else 'Renamed'} {len(renamed)} file(s):")
        for old_path, new_path in renamed:
            print(f"  {Path(old_path).name} → {Path(new_path).name}")

        if args.dry_run:
            print(f"\nRun without --dry-run to actually rename the files.")
    else:
        print(f"\nNo files were renamed.")
        
    staged_files()

    main(target_version=args.target, prior_version=args.source)
    
    staged_files()


# Example usage of rename_chain_upgrade_configs function:
#
# To rename all chain upgrade configs from 4.21 to 4.22:
#
#   from update_staged_configs_for_chain_upgrade import rename_chain_upgrade_configs
#
#   # Dry run to see what would be renamed (excludes automated-release-stable by default)
#   rename_chain_upgrade_configs("4.21", "4.22", dry_run=True)
#
#   # Actually rename the files
#   renamed = rename_chain_upgrade_configs("4.21", "4.22", dry_run=False)
#   print(f"Renamed {len(renamed)} files")
#
#   # Include automated-release-stable configs
#   renamed = rename_chain_upgrade_configs("4.21", "4.22", exclude_automated=False)
#
# Or run directly in Python:
#
#   python3 -c "from tools.update_staged_configs_for_chain_upgrade import rename_chain_upgrade_configs; rename_chain_upgrade_configs('4.21', '4.22')"
