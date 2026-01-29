# Obsidian H1 → H2 Converter

A Python script that safely converts Markdown H1 headings (`# Title`) to H2 headings (`## Title`) across an Obsidian vault.

## Features

- **Recursive scanning** of all `.md` files in a vault
- **Safe by default** - dry-run mode previews changes without modifying files
- **Atomic writes** - changes are written to temp files, then renamed (prevents corruption)
- **Timestamped backups** - stored in `_backups/` folder at vault root
- **Smart detection** - only converts true H1 headings with a space after `#`
- **Preserves content** - skips fenced code blocks, YAML frontmatter, and existing H2+ headings
- **Cross-platform** - works on Windows, macOS, and Linux

## Requirements

- Python 3.10+ (uses `|` union type hints)
- No external dependencies (stdlib only)

## Installation

1. Download `convert_h1_to_h2.py` to any location
2. Run with Python 3

## Usage

### Basic Commands

```bash
# Dry run (default) — see what would change
python convert_h1_to_h2.py /path/to/vault

# Dry run with per-file details
python convert_h1_to_h2.py /path/to/vault --verbose

# Apply changes (with backups)
python convert_h1_to_h2.py /path/to/vault --write

# Apply changes without backups (use with caution)
python convert_h1_to_h2.py /path/to/vault --write --no-backup

# Exclude specific folders
python convert_h1_to_h2.py /path/to/vault --exclude "drafts,templates"
```

### CLI Arguments

| Argument | Description |
|----------|-------------|
| `vault_path` | **(Required)** Path to the Obsidian vault root |
| `--dry-run` | Preview changes without modifying (default: on) |
| `--write` | Actually modify files |
| `--backup` | Create backups before modifying (default: on) |
| `--no-backup` | Skip creating backups |
| `--verbose`, `-v` | Show per-file replacement counts |
| `--exclude "a,b"` | Comma-separated folder names to skip |

## What Gets Converted

| Input | Output | Changed? |
|-------|--------|----------|
| `# Title` | `## Title` | ✅ Yes |
| `  # Indented` | `  ## Indented` | ✅ Yes (up to 3 spaces) |
| `## Already H2` | `## Already H2` | ❌ No |
| `### Deeper` | `### Deeper` | ❌ No |
| `#tag` | `#tag` | ❌ No (no space) |
| `#Title` | `#Title` | ❌ No (no space) |
| Inside ` ``` ` blocks | Unchanged | ❌ No |
| YAML frontmatter | Unchanged | ❌ No |

## Automatically Excluded

The following are always skipped:
- Hidden files/folders (starting with `.`)
- `.obsidian/`
- `.git/`
- `.trash/`
- `node_modules/`

## Backup System

When running with `--write` (and `--backup`, which is on by default):

1. A `_backups/` folder is created at vault root
2. Original folder structure is mirrored inside
3. Files are named with timestamps: `note_20260121_174532.md`
4. Multiple runs create multiple timestamped copies

**Example backup structure:**
```
vault/
├── _backups/
│   ├── note_20260121_174532.md
│   └── subfolder/
│       └── other_20260121_174535.md
├── note.md
└── subfolder/
    └── other.md
```

## Safety Guarantees

1. **Dry-run is default** - must explicitly use `--write` to modify
2. **Atomic writes** - temp file → rename prevents partial writes
3. **Encoding detection** - tries UTF-8, UTF-8-BOM, Latin-1
4. **No silent failures** - errors are reported in summary
5. **Idempotent** - running twice won't double-convert H2 to H3

## Example Output

```
============================================================
Obsidian H1 → H2 Converter
============================================================
Vault path: C:\Users\Me\Documents\MyVault
Mode: DRY RUN (no files will be modified)
============================================================

Found 142 Markdown file(s) to scan.

============================================================
SUMMARY
============================================================
Files scanned:      142
Files with H1s:     23
Total H1 headings:  47

⚠️  DRY RUN: No files were modified.
   Run with --write to apply changes.
============================================================
```

## License

- MIT
