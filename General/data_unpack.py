#!/usr/bin/env python3

import os

import sys

import shutil

import tarfile

import zipfile

import gzip

import bz2

import lzma

from pathlib import Path

import py7zr



# Archives we recognize

ARCHIVE_SUFFIXES = (# found: .zip .7z .gz

    ".zip",

    ".tar",

    ".tar.gz",

    ".tgz",

    ".tar.bz2",

    ".tbz2",

    ".tar.xz",

    ".txz",

    ".gz",

    ".bz2",

    ".xz",

    ".7z",   # detected, not extracted by stdlib

    ".rar",  # detected, not extracted by stdlib

)



# Archives we can extract with stdlib

SUPPORTED_EXTRACT_SUFFIXES = (

    ".zip",

    ".tar",

    ".tar.gz",

    ".tgz",

    ".tar.bz2",

    ".tbz2",

    ".tar.xz",

    ".txz",

    ".gz",

    ".bz2",

    ".xz",

    ".7z"

)



def is_archive(path: Path) -> bool:

    n = path.name.lower()

    return any(n.endswith(sfx) for sfx in ARCHIVE_SUFFIXES)



def is_supported_archive(path: Path) -> bool:

    n = path.name.lower()

    return any(n.endswith(sfx) for sfx in SUPPORTED_EXTRACT_SUFFIXES)

import re

from pathlib import Path



def sanitize_dirname(name: str) -> str:

    """

    Make a filesystem-friendly directory name:

    - remove dots

    - replace whitespace with underscore

    - replace other weird chars with underscore

    - collapse repeated underscores

    """

    name = name.replace(".", "")                 # <- your requirement

    name = re.sub(r"\s+", "_", name)

    name = re.sub(r"[^A-Za-z0-9_-]+", "_", name) # keep simple safe set

    name = re.sub(r"_+", "_", name).strip("_")

    return name or "extracted"



import hashlib

#counter = 0

import hashlib

from pathlib import Path



def dest_dir_for_archive(archive_path: Path) -> Path:

    # short stable id from full path, not just filename

    key = str(archive_path).lower()

    short = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]

    return archive_path.with_name(f"x_{short}")



def ensure_within_dir(base_dir: Path, target: Path) -> None:

    base_dir = base_dir.resolve()

    target = target.resolve()

    if not str(target).startswith(str(base_dir) + os.sep) and target != base_dir:

        raise RuntimeError(f"Unsafe path traversal detected: {target} not within {base_dir}")



def safe_extract_zip(zip_path: Path, out_dir: Path) -> None:

    with zipfile.ZipFile(zip_path) as z:

        for member in z.infolist():

            member_path = Path(member.filename)

            if member_path.is_absolute():

                raise RuntimeError(f"Refusing absolute path in zip: {member.filename}")

            out_path = out_dir / member.filename

            ensure_within_dir(out_dir, out_path)

        z.extractall(out_dir)



def safe_extract_tar(tar_path: Path, out_dir: Path) -> None:

    with tarfile.open(tar_path, "r:*") as t:

        for member in t.getmembers():

            member_path = Path(member.name)

            if member_path.is_absolute() or ".." in member_path.parts:

                raise RuntimeError(f"Unsafe path in tar: {member.name}")



            out_path = out_dir / member.name

            ensure_within_dir(out_dir, out_path)



            if member.issym() or member.islnk():

                raise RuntimeError(f"Refusing links in tar: {member.name}")



        t.extractall(out_dir)



def extract_7z_py(archive_path: Path, out_dir: Path) -> None:

    out_dir.mkdir(parents=True, exist_ok=True)



    with py7zr.SevenZipFile(archive_path, mode="r") as z:

        for name in z.getnames():

            p = Path(name)

            if p.is_absolute() or ".." in p.parts:

                raise RuntimeError(f"Unsafe path in 7z archive: {name}")

        z.extractall(path=out_dir)



def decompress_single_file(archive_path: Path, out_dir: Path) -> None:

    name = archive_path.name

    lower = name.lower()



    if lower.endswith(".gz") and not (lower.endswith(".tar.gz") or lower.endswith(".tgz")):

        opener = gzip.open

        out_name = name[:-3]

    elif lower.endswith(".bz2") and not (lower.endswith(".tar.bz2") or lower.endswith(".tbz2")):

        opener = bz2.open

        out_name = name[:-4]

    elif lower.endswith(".xz") and not (lower.endswith(".tar.xz") or lower.endswith(".txz")):

        opener = lzma.open

        out_name = name[:-3]

    else:

        raise RuntimeError("Not a supported single-file compression format")



    out_dir.mkdir(parents=True, exist_ok=True)



    # keep original name if possible, but fall back to short name if too long

    out_path = out_dir / out_name

    try:

        ensure_within_dir(out_dir, out_path)

        with opener(archive_path, "rb") as f_in, open(out_path, "wb") as f_out:

            shutil.copyfileobj(f_in, f_out)

    except OSError:

        short_name = "payload"

        out_path = out_dir / short_name

        ensure_within_dir(out_dir, out_path)

        with opener(archive_path, "rb") as f_in, open(out_path, "wb") as f_out:

            shutil.copyfileobj(f_in, f_out)

    

def extract_archive(archive_path: Path, verbose: bool = True) -> bool:

    out_dir = dest_dir_for_archive(archive_path)



    # idempotent: skip if already extracted and non-empty

    if out_dir.exists() and any(out_dir.iterdir()):

        if verbose:

            print(f"SKIP (already extracted): {archive_path} -> {out_dir}")

        return False



    out_dir.mkdir(parents=True, exist_ok=True)

    lower = archive_path.name.lower()



    if verbose:

        print(f"EXTRACT: {archive_path} -> {out_dir}")



    try:

        if lower.endswith(".zip"):

            safe_extract_zip(archive_path, out_dir)

        elif lower.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):

            safe_extract_tar(archive_path, out_dir)

        elif lower.endswith((".gz", ".bz2", ".xz")):

            decompress_single_file(archive_path, out_dir)

        elif lower.endswith(".7z"):

            extract_7z_py(archive_path, out_dir)

        else:

            raise RuntimeError(f"Unsupported archive type: {archive_path.name}")

    except Exception:

        # cleanup empty dir on failure

        try:

            if out_dir.exists() and not any(out_dir.iterdir()):

                out_dir.rmdir()

        except Exception:

            pass

        raise



    return True



def clone_everything(src_root: Path, dst_root: Path, verbose: bool = True) -> tuple[int, int]:

    """

    Copy ALL files. Returns (files_copied, archives_copied).

    """

    files_copied = 0

    archives_copied = 0



    for p in src_root.rglob("*"):

        if p.is_dir():

            continue

        rel = p.relative_to(src_root)

        dst = dst_root / rel

        dst.parent.mkdir(parents=True, exist_ok=True)



        shutil.copy2(p, dst)

        files_copied += 1

        if is_archive(p):

            archives_copied += 1



        if verbose and files_copied % 500 == 0:

            print(f"Copied {files_copied} files...")



    return files_copied, archives_copied



def find_supported_archives(root: Path) -> list[Path]:

    return sorted([p for p in root.rglob("*") if p.is_file() and is_supported_archive(p)])



def find_unsupported_archives(root: Path) -> list[Path]:

    # .7z/.rar etc that we recognize but can't extract

    out = []

    for p in root.rglob("*"):

        if not p.is_file():

            continue

        if is_archive(p) and not is_supported_archive(p):

            out.append(p)

    return sorted(out)



def main() -> int:

    if len(sys.argv) < 3:

        print(

            "Usage: clone_all_and_unpack.py SRC_DIR DST_DIR "

            "[--max-rounds N] [--delete-archives] [--quiet]",

            file=sys.stderr

        )

        return 2



    src_root = Path(sys.argv[1]).expanduser().resolve()

    dst_root = Path(sys.argv[2]).expanduser().resolve()



    max_rounds = 50

    delete_archives = False

    verbose = True



    args = sys.argv[3:]

    i = 0

    while i < len(args):

        a = args[i]

        if a == "--max-rounds":

            i += 1

            max_rounds = int(args[i])

        elif a == "--delete-archives":

            delete_archives = True

        elif a == "--quiet":

            verbose = False

        else:

            print(f"Unknown arg: {a}", file=sys.stderr)

            return 2

        i += 1



    if not src_root.is_dir():

        print(f"ERROR: source is not a directory: {src_root}", file=sys.stderr)

        return 2



    if dst_root.exists() and any(dst_root.iterdir()):

        print(f"ERROR: destination exists and is not empty: {dst_root}", file=sys.stderr)

        return 2



    dst_root.mkdir(parents=True, exist_ok=True)



    if verbose:

        print(f"Cloning ALL files:\n  FROM: {src_root}\n  TO:   {dst_root}\n")



    files_copied, archives_copied = clone_everything(src_root, dst_root, verbose=verbose)



    if verbose:

        print(f"\nCopied files total: {files_copied}")

        print(f"Archives copied:    {archives_copied}")

        print("\nNow iteratively unpacking supported archives INSIDE the new dataset...")



    total_extracted = 0

    for round_idx in range(1, max_rounds + 1):

        remaining_supported = find_supported_archives(dst_root)

        if verbose:

            print(f"\nSupported archives still present: {len(remaining_supported)}")

            for ex in remaining_supported[:10]:

                print(f"  - {ex.relative_to(dst_root)}")



        extracted_this_round = 0

        for a in remaining_supported:

            try:

                if extract_archive(a, verbose=verbose):

                    extracted_this_round += 1

                    total_extracted += 1

                    if delete_archives:

                        a.unlink(missing_ok=True)

            except Exception as e:

                print(f"ERROR extracting {a}: {e}", file=sys.stderr)



        if extracted_this_round == 0:

            if verbose:

                print("\nNo new archives extracted. Done.")

            break



    unsupported = find_unsupported_archives(dst_root)

    if verbose:

        print(f"\nTotal archives extracted: {total_extracted}")

        if unsupported:

            print(f"Unsupported recognized archives present: {len(unsupported)}")

            # print a few examples

            for ex in unsupported[:10]:

                print(f"  - {ex.relative_to(dst_root)}")

        else:

            print("No unsupported archives detected.")



    return 0







if __name__ == "__main__":

    raise SystemExit(main())

