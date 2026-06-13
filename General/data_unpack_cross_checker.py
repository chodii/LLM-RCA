# -*- coding: utf-8 -*-

"""

Created on Mon Mar  9 13:18:31 2026



@author: chodo

"""



from __future__ import annotations



import argparse

import bz2

import gzip

import json

import lzma

import os

import shutil

import tarfile

import tempfile

import zipfile

from pathlib import Path

from typing import Iterable, Optional





# Multi-part suffixes first, so matching is unambiguous.

ARCHIVE_SUFFIXES = (

    ".tar.gz",

    ".tar.bz2",

    ".tar.xz",

    ".tgz",

    ".tbz2",

    ".txz",

    ".tar",

    ".zip",

    ".gz",

    ".bz2",

    ".xz",

    ".7z",

)





def is_archive(path: Path) -> Optional[str]:

    name = path.name.lower()

    for suffix in ARCHIVE_SUFFIXES:

        if name.endswith(suffix):

            return suffix

    return None





def iter_regular_files(root: Path) -> Iterable[Path]:

    for p in root.rglob("*"):

        if p.is_file():

            yield p





class UniqueNamer:

    def __init__(self, out_dir: Path, start: int = 0):

        self.out_dir = out_dir

        self.counter = start



    def reserve(self, src_name: str) -> Path:

        """

        Produce a unique destination filename.

        Counter-based naming means collisions are impossible unless the counter repeats.

        """

        ext = "".join(Path(src_name).suffixes)

        while True:

            name = f"{self.counter:012d}{ext}"

            self.counter += 1

            dst = self.out_dir / name

            if dst.exists():

                # This should never happen unless the output folder is reused incorrectly.

                raise RuntimeError(f"Refusing to overwrite existing file: {dst}")

            return dst





def safe_copy_file(src: Path, dst: Path) -> int:

    if dst.exists():

        raise RuntimeError(f"Refusing to overwrite existing file: {dst}")

    shutil.copy2(src, dst)

    return dst.stat().st_size





def safe_move_file(src: Path, dst: Path) -> int:

    if dst.exists():

        raise RuntimeError(f"Refusing to overwrite existing file: {dst}")

    shutil.move(str(src), str(dst))

    return dst.stat().st_size





def decompress_single_file(src: Path, out_dir: Path) -> list[Path]:

    """

    Handle .gz / .bz2 / .xz as single-file compression.

    Output is one decompressed file in out_dir.

    """

    suffix = is_archive(src)

    if suffix not in {".gz", ".bz2", ".xz"}:

        raise ValueError(f"Not a single-file compression format: {src}")



    # Remove only the last compression suffix.

    if suffix == ".gz":

        base_name = src.name[:-3] or "decompressed"

        opener = gzip.open

    elif suffix == ".bz2":

        base_name = src.name[:-4] or "decompressed"

        opener = bz2.open

    else:  # .xz

        base_name = src.name[:-3] or "decompressed"

        opener = lzma.open



    out_path = out_dir / base_name

    with opener(src, "rb") as fin, open(out_path, "wb") as fout:

        shutil.copyfileobj(fin, fout)



    return [out_path]





def extract_archive(src: Path, out_dir: Path) -> None:

    """

    Extract archive contents into out_dir.



    Supported with stdlib:

      .zip, .tar, .tar.gz, .tgz, .tar.bz2, .tbz2, .tar.xz, .txz, .gz, .bz2, .xz



    Optional:

      .7z via py7zr

    """

    suffix = is_archive(src)

    if suffix is None:

        raise ValueError(f"Not an archive: {src}")



    if suffix == ".zip":

        with zipfile.ZipFile(src, "r") as zf:

            zf.extractall(out_dir)

        return



    if suffix in {".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz"}:

        with tarfile.open(src, "r:*") as tf:

            tf.extractall(out_dir)

        return



    if suffix in {".gz", ".bz2", ".xz"}:

        decompress_single_file(src, out_dir)

        return



    if suffix == ".7z":

        try:

            import py7zr  # type: ignore

        except ImportError as e:

            raise RuntimeError(

                "Found a .7z archive, but py7zr is not installed. "

                "Install it with: pip install py7zr"

            ) from e



        with py7zr.SevenZipFile(src, mode="r") as zf:

            zf.extractall(path=out_dir)

        return



    raise RuntimeError(f"Unsupported archive type: {src}")





def process_round(in_dir: Path, out_dir: Path, manifest_dir: Path, start_counter: int) -> int:

    out_dir.mkdir(parents=True, exist_ok=False)

    manifest_dir.mkdir(parents=True, exist_ok=True)



    namer = UniqueNamer(out_dir, start=start_counter)



    discovered_inputs = sorted(iter_regular_files(in_dir))

    processed_inputs = 0

    copied_outputs = 0

    extracted_outputs = 0

    bytes_in = 0

    bytes_out = 0



    manifest_path = manifest_dir / "manifest.jsonl"

    summary_path = manifest_dir / "summary.json"



    with open(manifest_path, "w", encoding="utf-8") as mf:

        for src in discovered_inputs:

            processed_inputs += 1

            src_size = src.stat().st_size

            bytes_in += src_size



            archive_suffix = is_archive(src)



            if archive_suffix is None:

                dst = namer.reserve(src.name)

                out_size = safe_copy_file(src, dst)

                copied_outputs += 1

                bytes_out += out_size



                record = {

                    "type": "copied_file",

                    "input": str(src),

                    "input_size": src_size,

                    "output": str(dst),

                    "output_size": out_size,

                }

                mf.write(json.dumps(record) + "\n")

                continue



            with tempfile.TemporaryDirectory(prefix="extract_round_") as tmp:

                tmp_dir = Path(tmp)



                extract_archive(src, tmp_dir)

                extracted_files = sorted(iter_regular_files(tmp_dir))



                record = {

                    "type": "archive",

                    "input": str(src),

                    "input_size": src_size,

                    "archive_suffix": archive_suffix,

                    "outputs": [],

                }



                for extracted in extracted_files:

                    dst = namer.reserve(extracted.name)

                    out_size = safe_move_file(extracted, dst)

                    extracted_outputs += 1

                    bytes_out += out_size



                    record["outputs"].append(

                        {

                            "from_extracted_path": str(extracted),

                            "output": str(dst),

                            "output_size": out_size,

                        }

                    )



                mf.write(json.dumps(record) + "\n")



    if processed_inputs != len(discovered_inputs):

        raise RuntimeError(

            f"Sanity check failed: processed {processed_inputs}, discovered {len(discovered_inputs)}"

        )



    summary = {

        "input_dir": str(in_dir),

        "output_dir": str(out_dir),

        "discovered_input_files": len(discovered_inputs),

        "processed_input_files": processed_inputs,

        "copied_outputs": copied_outputs,

        "extracted_outputs": extracted_outputs,

        "total_outputs": copied_outputs + extracted_outputs,

        "total_input_bytes": bytes_in,

        "total_output_bytes": bytes_out,

        "next_counter": namer.counter,

    }



    with open(summary_path, "w", encoding="utf-8") as sf:

        json.dump(summary, sf, indent=2)



    return namer.counter





def run(root: Path, rounds: int) -> None:

    """

    Expect root/0 to exist.

    Create root/1, root/2, ..., root/N.

    Also create root/manifests/<round>/...

    """

    current_counter = 0



    for i in range(rounds):

        in_dir = root / str(i)

        out_dir = root / str(i + 1)

        manifest_dir = root / "manifests" / f"{i}_to_{i+1}"



        if not in_dir.exists():

            raise RuntimeError(f"Input folder does not exist: {in_dir}")

        if out_dir.exists():

            raise RuntimeError(f"Output folder already exists: {out_dir}")



        print(f"Processing round {i} -> {i+1}")

        current_counter = process_round(

            in_dir=in_dir,

            out_dir=out_dir,

            manifest_dir=manifest_dir,

            start_counter=current_counter,

        )



    print("Done.")





def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(

        "--root",

        type=Path,

        required=True,

        help="Root directory containing folder 0",

    )

    parser.add_argument(

        "--rounds",

        type=int,

        required=True,

        help="Number of rounds. Creates 1..N from 0.",

    )

    args = parser.parse_args()



    run(args.root, args.rounds)





if __name__ == "__main__":

    main()