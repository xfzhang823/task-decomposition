#!/usr/bin/env python3
"""Print a recursive directory tree for a target path.

Example CLI usage:

    python tree.py
    python tree.py /path/to/project
    python tree.py --dirs-only .
    python tree.py --output tree.txt /path/to/project
    python tree.py --exclude custom_dir docs

The script prints the resolved root directory name first, then a tree of
child entries using unicode connectors.

Common directories like __pycache__, venv, .venv, .git, node_modules,
.pytest_cache, .mypy_cache, .idea, .vscode, __pycache__, dist, build,
*.egg-info, .next, .nuxt, .cache, .github, .DS_Store, .env are automatically excluded.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO


def iter_entries(
    path: Path, dirs_only: bool, exclude_dirs: set[str] | None = None
) -> list[Path]:
    """Return sorted entries for a directory.

    Excludes __pycache__ and sorts with directories first, then files alphabetically.

    Args:
        path: Directory to inspect.
        dirs_only: If True, return directories only.
        exclude_dirs: Set of directory names to exclude (e.g., {'venv', '.git'}).

    Example:
        entries = iter_entries(Path("/path/to/project"), dirs_only=False)
        # entries might look like:
        # [Path(".../src"), Path(".../README.md")]
    """
    if exclude_dirs is None:
        exclude_dirs = set()

    entries = []
    for entry in path.iterdir():
        # Skip if directory is in exclude list
        if entry.is_dir() and entry.name in exclude_dirs:
            continue

        if dirs_only and not entry.is_dir():
            continue

        entries.append(entry)

    return sorted(entries, key=lambda p: (p.is_file(), p.name.lower()))


def display_tree(
    path: Path,
    prefix: str = "",
    dirs_only: bool = False,
    output_file: TextIO | None = None,
    exclude_dirs: set[str] | None = None,
) -> None:
    """Recursively print a tree structure starting from the given path.

    Uses unicode connectors to visually represent directory hierarchy.

    Args:
        path: Directory to render.
        prefix: Prefix used for nested tree branches.
        dirs_only: If True, print only directories.
        output_file: File object to write to (default: stdout).
        exclude_dirs: Set of directory names to exclude.

    Example:
        display_tree(Path("/path/to/project"))

        Possible output:
            ├── src
            │   └── app.py
            └── README.md
    """
    if output_file is None:
        output_file = sys.stdout

    entries = iter_entries(path, dirs_only, exclude_dirs)
    for idx, entry in enumerate(entries):
        is_last = idx == len(entries) - 1
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{entry.name}", file=output_file)

        if entry.is_dir():
            child_prefix = prefix + ("    " if is_last else "│   ")
            display_tree(
                entry,
                child_prefix,
                dirs_only=dirs_only,
                output_file=output_file,
                exclude_dirs=exclude_dirs,
            )


def save_tree_to_file(
    root: Path, output_path: Path, dirs_only: bool, exclude_dirs: set[str] | None = None
) -> None:
    """Save the directory tree to a file.

    Args:
        root: Root directory to generate tree from.
        output_path: Path to the output file.
        dirs_only: If True, show directories only.
        exclude_dirs: Set of directory names to exclude.

    Raises:
        OSError: If the file cannot be written.

    Example:
        save_tree_to_file(Path("/path/to/project"), Path("tree.txt"), dirs_only=False)
    """
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            print(root.name, file=f)
            display_tree(
                root, dirs_only=dirs_only, output_file=f, exclude_dirs=exclude_dirs
            )
        print(f"✅ Tree saved to: {output_path}")
    except OSError as e:
        raise SystemExit(f"Error: cannot write to file {output_path}: {e}")


def get_default_excludes() -> set[str]:
    """Return set of default directories to exclude.

    Returns:
        Set of directory names that should be excluded by default.

    Example:
        defaults = get_default_excludes()
        # {'__pycache__', 'venv', '.git', 'node_modules', ...}
    """
    return {
        # Python
        "__pycache__",
        "venv",
        ".venv",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
        "*.egg-info",
        ".ruff_cache",  # 🆕 Ruff linter/cache
        ".agents",  # 🆕 AI agent tools
        # JavaScript/Node
        "node_modules",
        ".next",
        ".nuxt",
        ".cache",
        ".vite",  # 🆕 Vite build tool cache
        ".vitest",  # 🆕 Vitest testing cache
        # Git
        ".git",
        ".github",
        # IDE
        ".idea",
        ".vscode",
        # System
        ".DS_Store",
        # Environment
        ".env",
    }


def main() -> None:
    """Parse CLI arguments and print the directory tree for the target path.

    Example:
        Run from the command line:

            python tree.py /path/to/project
            python tree.py --output tree.txt /path/to/project
            python tree.py --dirs-only --output structure.txt .
            python tree.py --exclude custom_dir docs --no-default-excludes
            python tree.py -e venv .git --output tree.txt
    """
    parser = argparse.ArgumentParser(
        description="Print a recursive directory tree.",
        epilog="""Examples:
  %(prog)s                              # Tree of current directory
  %(prog)s /path/to/project             # Tree of specific directory
  %(prog)s --dirs-only .                # Directories only
  %(prog)s --output tree.txt            # Save tree to file
  %(prog)s --exclude docs temp          # Exclude additional directories
  %(prog)s --no-default-excludes        # Don't exclude common directories
        """,
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Directory to inspect (default: current directory).",
    )
    parser.add_argument(
        "--dirs-only",
        action="store_true",
        help="Show directories only.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Save the tree to a file instead of printing to stdout.",
    )
    parser.add_argument(
        "--exclude",
        "-e",
        nargs="+",
        metavar="DIR",
        help="Additional directory names to exclude (can specify multiple).",
    )
    parser.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="Don't exclude common directories (__pycache__, venv, .git, node_modules, etc.).",
    )

    args = parser.parse_args()
    root = Path(args.target).expanduser().resolve()

    if not root.exists():
        raise SystemExit(f"Error: path does not exist: {root}")

    if not root.is_dir():
        raise SystemExit(f"Error: path is not a directory: {root}")

    # Build exclude set
    exclude_dirs = set()

    # Add default excludes unless disabled
    if not args.no_default_excludes:
        exclude_dirs.update(get_default_excludes())

    # Add user-specified excludes
    if args.exclude:
        exclude_dirs.update(args.exclude)

    # Print info about excludes if any (optional, uncomment if desired)
    # if exclude_dirs:
    #     print(f"Excluding: {', '.join(sorted(exclude_dirs))}", file=sys.stderr)

    # Handle output to file if specified
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        save_tree_to_file(root, output_path, args.dirs_only, exclude_dirs)
    else:
        # Print to console
        print(root.name)
        display_tree(root, dirs_only=args.dirs_only, exclude_dirs=exclude_dirs)


if __name__ == "__main__":
    main()
