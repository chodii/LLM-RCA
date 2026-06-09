# -*- coding: utf-8 -*-
"""
Created on Wed Jan 28 18:57:04 2026

@author: chodo
"""

#!/usr/bin/env python3
import os
import sys
from collections import Counter, defaultdict

ARCHIVE_EXTS = {
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".xz", ".txz",
    ".7z", ".rar", ".zst", ".lz4", ".cab", ".iso", ".dmg"
}

def is_archive(filename: str) -> bool:
    name = filename.lower()
    # Handle double extensions like .tar.gz
    if name.endswith(".tar.gz") or name.endswith(".tar.bz2") or name.endswith(".tar.xz") or name.endswith(".tar.zst"):
        return True
    _, ext = os.path.splitext(name)
    return ext in ARCHIVE_EXTS

def main(root: str) -> int:
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        print(f"ERROR: Not a directory: {root}", file=sys.stderr)
        return 2

    non_archive_files = []
    ext_counter = Counter()
    ext_examples = defaultdict(list)

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden dirs if you want (uncomment next lines)
        # dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if is_archive(fn):
                continue
            non_archive_files.append(full)

            lower = fn.lower()
            _, ext = os.path.splitext(lower)
            ext = ext if ext else "<no_ext>"
            ext_counter[ext] += 1
            if len(ext_examples[ext]) < 5:
                ext_examples[ext].append(os.path.relpath(full, root))

    # Print file list
    for p in non_archive_files:
        print(os.path.relpath(p, root))

    # Print summary to stderr (so you can redirect file list cleanly)
    print("\n--- SUMMARY (non-archive) ---", file=sys.stderr)
    total = sum(ext_counter.values())
    print(f"Total non-archive files: {total}", file=sys.stderr)
    for ext, c in ext_counter.most_common():
        print(f"{ext:10s}  {c:8d}", file=sys.stderr)
        for ex in ext_examples[ext]:
            print(f"   - {ex}", file=sys.stderr)

    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} /path/to/dataset", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
