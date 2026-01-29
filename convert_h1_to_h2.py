#!/usr/bin/env python3
"""
convert_h1_to_h2.py - Convert Markdown H1 headings to H2 in an Obsidian vault.

Features:
    - Recursive directory scanning with smart exclusions
    - Safe handling of fenced code blocks (``` and ~~~)
    - Preserves YAML frontmatter
    - Dry-run mode (default) to preview changes
    - Atomic file writes to prevent corruption
    - Timestamped backups before modifications

Usage:
    python convert_h1_to_h2.py /path/to/vault              # Dry run (preview)
    python convert_h1_to_h2.py /path/to/vault --write      # Apply changes
    python convert_h1_to_h2.py /path/to/vault --exclude "drafts,templates"
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import NamedTuple


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class ConversionResult(NamedTuple):
    """Result of processing a single Markdown file."""
    file_path: Path
    replacements: int
    modified: bool
    error: str | None = None


class ConversionSummary(NamedTuple):
    """Aggregated summary of the entire conversion run."""
    files_scanned: int
    files_changed: int
    total_replacements: int
    errors: list[str]


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_EXCLUDES = {".obsidian", ".git", "node_modules", ".trash", ".DS_Store"}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_hidden(path: Path) -> bool:
    """Check if any component of a path is hidden (starts with a dot)."""
    return any(part.startswith(".") for part in path.parts)


def should_exclude(path: Path, vault_root: Path, extra_excludes: set[str]) -> bool:
    """
    Determine if a file path should be excluded from processing.
    
    Args:
        path: Absolute path to the file being considered.
        vault_root: Absolute path to the vault's root directory.
        extra_excludes: Set of additional folder names to skip.
    
    Returns:
        True if the file should be skipped, False if it should be processed.
    """
    try:
        rel_path = path.relative_to(vault_root)
    except ValueError:
        return True
    
    all_excludes = DEFAULT_EXCLUDES | extra_excludes
    
    for part in rel_path.parts:
        if part.startswith(".") or part in all_excludes:
            return True
    
    return False


def find_markdown_files(vault_path: Path, extra_excludes: set[str]) -> list[Path]:
    """
    Recursively find all Markdown files (.md) in the vault.
    
    Args:
        vault_path: Absolute path to the vault's root directory.
        extra_excludes: Set of additional folder names to skip.
    
    Returns:
        A sorted list of Path objects pointing to .md files.
    """
    md_files = []
    
    for root, dirs, files in os.walk(vault_path):
        root_path = Path(root)
        
        # Modify dirs in-place to prevent os.walk from descending into excluded folders
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in (DEFAULT_EXCLUDES | extra_excludes)
        ]
        
        for filename in files:
            if not filename.endswith(".md") or filename.startswith("."):
                continue
            
            file_path = root_path / filename
            if not should_exclude(file_path, vault_path, extra_excludes):
                md_files.append(file_path)
    
    return sorted(md_files)


# =============================================================================
# CORE CONVERSION LOGIC
# =============================================================================

def convert_h1_to_h2(content: str) -> tuple[str, int]:
    """
    Convert H1 headings to H2 headings in Markdown content.
    
    Converts "# Title" to "## Title" while preserving:
    - Lines inside fenced code blocks (``` or ~~~)
    - YAML frontmatter (--- block at file start)
    - Headings already H2 or deeper
    - Hashtags without space after # (e.g., #tag)
    - Indentation (up to 3 spaces before #)
    
    Args:
        content: The complete file content as a string.
    
    Returns:
        Tuple of (new_content, replacement_count).
    """
    lines = content.split("\n")
    result_lines = []
    replacement_count = 0
    
    # State tracking for protected regions
    in_frontmatter = False
    in_code_block = False
    code_fence_pattern = None
    
    # Regex: 0-3 leading spaces, then "# " (hash + space), then rest of line
    h1_pattern = re.compile(r"^( {0,3})(# )(.*)$")
    
    for i, line in enumerate(lines):
        # Handle YAML frontmatter (must start on line 0)
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            result_lines.append(line)
            continue
        
        if in_frontmatter:
            result_lines.append(line)
            if line.strip() == "---":
                in_frontmatter = False
            continue
        
        # Handle fenced code blocks
        stripped = line.lstrip()
        
        if not in_code_block:
            if stripped.startswith("```"):
                in_code_block = True
                code_fence_pattern = "```"
                result_lines.append(line)
                continue
            elif stripped.startswith("~~~"):
                in_code_block = True
                code_fence_pattern = "~~~"
                result_lines.append(line)
                continue
        else:
            if stripped.startswith(code_fence_pattern):
                in_code_block = False
                code_fence_pattern = None
            result_lines.append(line)
            continue
        
        # Check for H1 heading and convert to H2
        match = h1_pattern.match(line)
        if match:
            leading_spaces = match.group(1)
            rest_of_line = match.group(3)
            new_line = f"{leading_spaces}## {rest_of_line}"
            result_lines.append(new_line)
            replacement_count += 1
        else:
            result_lines.append(line)
    
    return "\n".join(result_lines), replacement_count


# =============================================================================
# FILE SAFETY FUNCTIONS
# =============================================================================

def create_backup(file_path: Path, vault_root: Path) -> Path:
    """
    Create a timestamped backup of a file in _backups folder.
    
    Args:
        file_path: Absolute path to the file to backup.
        vault_root: Absolute path to the vault's root directory.
    
    Returns:
        Path to the newly created backup file.
    """
    backup_dir = vault_root / "_backups"
    backup_dir.mkdir(exist_ok=True)
    
    try:
        rel_path = file_path.relative_to(vault_root)
        backup_subdir = backup_dir / rel_path.parent
        backup_subdir.mkdir(parents=True, exist_ok=True)
    except ValueError:
        backup_subdir = backup_dir
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
    backup_path = backup_subdir / backup_name
    
    shutil.copy2(file_path, backup_path)
    return backup_path


def write_file_atomic(file_path: Path, content: str, encoding: str = "utf-8") -> None:
    """
    Write content to a file atomically using a temporary file.
    
    Writes to a temp file first, then atomically renames to prevent corruption
    if the program crashes mid-write.
    
    Args:
        file_path: Destination file path.
        content: String content to write.
        encoding: Character encoding (default: UTF-8).
    """
    dir_path = file_path.parent
    
    # Create temp file in same directory (required for atomic rename)
    fd, temp_path = tempfile.mkstemp(
        suffix=".tmp",
        prefix=f".{file_path.name}_",
        dir=dir_path
    )
    
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(content)
        Path(temp_path).replace(file_path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


# =============================================================================
# FILE PROCESSING
# =============================================================================

def process_file(
    file_path: Path,
    vault_root: Path,
    dry_run: bool,
    create_backups: bool,
    verbose: bool
) -> ConversionResult:
    """
    Process a single Markdown file: read, convert, and optionally write.
    
    Args:
        file_path: Absolute path to the Markdown file.
        vault_root: Absolute path to the vault root.
        dry_run: If True, only count changes without modifying.
        create_backups: If True, create backup before writing.
        verbose: If True, print per-file progress.
    
    Returns:
        ConversionResult with processing details.
    """
    try:
        # Try multiple encodings
        content = None
        encoding_used = "utf-8"
        
        for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                encoding_used = encoding
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            return ConversionResult(
                file_path=file_path,
                replacements=0,
                modified=False,
                error="Could not decode file with supported encodings"
            )
        
        new_content, replacements = convert_h1_to_h2(content)
        
        if replacements == 0:
            return ConversionResult(file_path=file_path, replacements=0, modified=False)
        
        if verbose:
            rel_path = file_path.relative_to(vault_root)
            print(f"  {rel_path}: {replacements} H1 heading(s) found")
        
        if dry_run:
            return ConversionResult(file_path=file_path, replacements=replacements, modified=False)
        
        if create_backups:
            backup_path = create_backup(file_path, vault_root)
            if verbose:
                print(f"    Backup created: {backup_path.name}")
        
        write_file_atomic(file_path, new_content, encoding=encoding_used)
        
        return ConversionResult(file_path=file_path, replacements=replacements, modified=True)
    
    except Exception as e:
        return ConversionResult(file_path=file_path, replacements=0, modified=False, error=str(e))


def run_conversion(
    vault_path: Path,
    dry_run: bool,
    create_backups: bool,
    verbose: bool,
    extra_excludes: set[str]
) -> ConversionSummary:
    """
    Run the H1 to H2 conversion on the entire vault.
    
    Args:
        vault_path: Absolute path to the vault's root directory.
        dry_run: If True, only preview changes.
        create_backups: If True, backup files before modifying.
        verbose: If True, print per-file details.
        extra_excludes: Set of additional folder names to skip.
    
    Returns:
        ConversionSummary with aggregate statistics.
    """
    print(f"\n{'=' * 60}")
    print("Obsidian H1 → H2 Converter")
    print(f"{'=' * 60}")
    print(f"Vault path: {vault_path}")
    print(f"Mode: {'DRY RUN (no files will be modified)' if dry_run else 'WRITE MODE'}")
    if not dry_run:
        print(f"Backups: {'Enabled' if create_backups else 'Disabled'}")
    if extra_excludes:
        print(f"Extra excludes: {', '.join(sorted(extra_excludes))}")
    print(f"{'=' * 60}\n")
    
    md_files = find_markdown_files(vault_path, extra_excludes)
    print(f"Found {len(md_files)} Markdown file(s) to scan.\n")
    
    if verbose:
        print("Processing files:")
    
    results: list[ConversionResult] = []
    for file_path in md_files:
        result = process_file(file_path, vault_path, dry_run, create_backups, verbose)
        results.append(result)
    
    files_changed = sum(1 for r in results if r.replacements > 0)
    total_replacements = sum(r.replacements for r in results)
    errors = [f"{r.file_path}: {r.error}" for r in results if r.error]
    
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Files scanned:      {len(md_files)}")
    print(f"Files with H1s:     {files_changed}")
    print(f"Total H1 headings:  {total_replacements}")
    
    if dry_run and files_changed > 0:
        print(f"\n⚠️  DRY RUN: No files were modified.")
        print("   Run with --write to apply changes.")
    elif not dry_run and files_changed > 0:
        print(f"\n✅ {files_changed} file(s) modified.")
        if create_backups:
            print(f"   Backups saved to: {vault_path / '_backups'}")
    elif files_changed == 0:
        print("\n✅ No H1 headings found. No changes needed.")
    
    if errors:
        print(f"\n⚠️  Errors ({len(errors)}):")
        for err in errors:
            print(f"   - {err}")
    
    print(f"{'=' * 60}\n")
    
    return ConversionSummary(
        files_scanned=len(md_files),
        files_changed=files_changed,
        total_replacements=total_replacements,
        errors=errors
    )


# =============================================================================
# COMMAND-LINE INTERFACE
# =============================================================================

def parse_excludes(exclude_str: str | None) -> set[str]:
    """Parse comma-separated exclude string into a set of folder names."""
    if not exclude_str:
        return set()
    return {e.strip() for e in exclude_str.split(",") if e.strip()}


def main() -> int:
    """Main entry point. Returns exit code (0=success, 1=error)."""
    parser = argparse.ArgumentParser(
        description="Convert Markdown H1 headings to H2 headings in an Obsidian vault.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python convert_h1_to_h2.py /path/to/vault              # Dry run
  python convert_h1_to_h2.py /path/to/vault --write      # Apply changes
  python convert_h1_to_h2.py /path/to/vault --write -v   # Verbose
  python convert_h1_to_h2.py /path/to/vault --exclude "drafts,archive"

Safety:
  - Dry run is the default. Use --write to modify files.
  - Backups are created in <vault>/_backups/ with timestamps.
  - Files are written atomically (temp file, then rename).
        """
    )
    
    parser.add_argument("vault_path", type=str, help="Path to the Obsidian vault root")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview changes without modifying (default)")
    parser.add_argument("--write", action="store_true",
                        help="Actually modify files")
    parser.add_argument("--backup", action="store_true", default=True,
                        help="Create backups before modifying (default)")
    parser.add_argument("--no-backup", action="store_true",
                        help="Skip creating backups")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print per-file details")
    parser.add_argument("--exclude", type=str, default="",
                        help="Comma-separated folder names to exclude")
    
    args = parser.parse_args()
    
    vault_path = Path(args.vault_path).resolve()
    
    if not vault_path.exists():
        print(f"❌ Error: Vault path does not exist: {vault_path}", file=sys.stderr)
        return 1
    
    if not vault_path.is_dir():
        print(f"❌ Error: Vault path is not a directory: {vault_path}", file=sys.stderr)
        return 1
    
    dry_run = not args.write
    create_backups = args.backup and not args.no_backup
    extra_excludes = parse_excludes(args.exclude)
    
    summary = run_conversion(
        vault_path=vault_path,
        dry_run=dry_run,
        create_backups=create_backups,
        verbose=args.verbose,
        extra_excludes=extra_excludes
    )
    
    return 1 if summary.errors else 0


if __name__ == "__main__":
    sys.exit(main())
