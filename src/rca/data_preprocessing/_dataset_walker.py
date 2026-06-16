# -*- coding: utf-8 -*-

"""

Created on Fri Feb 20 20:14:52 2026



@author: chodo

"""





import os

from pathlib import Path

def dataset_iterator(root: Path):

    for current_dir, subdirs, files in os.walk(root):

        for filename in files:

            fp = os.path.join(current_dir, filename)

            if not os.path.isfile(fp):

                continue

            yield fp





def dataset_crude_iterator(root: Path):

    for current_dir, subdirs, files in os.walk(root):

        for filename in files:

            fp = os.path.join(current_dir, filename)

            if not os.path.isfile(fp):

                continue

            yield current_dir, filename



from typing import Iterable

def iter_spec_files(root: Path, ext="json") -> Iterable[Path]:

    for fp in root.rglob("*."+ext):

        if fp.is_file():

            yield fp



def parse_suffixes(fp):

    dirs = fp.split("\\")

    if len(dirs) == 1:

        return

    parts = dirs[-1].split(".")

    suffixes = [None]

    if not len(parts) == 1:

        suffixes = parts[1:]

    return suffixes



def unique_name(filename, reserved_names, POST_COUNT=False) -> str:

    if filename not in reserved_names:

        reserved_names[filename] = 0

    reserved_names[filename] += 1

    if not POST_COUNT:

        filename = str(reserved_names[filename]) + "-"+filename

    else:

        filename = filename+"-"+str(reserved_names[filename])

    return filename





def iter_files(root, ignore=None):

    """

    Iterate over all files under `root` and yield those whose names

    are not in the ignore list.



    Parameters

    ----------

    root : str

        Root folder to walk through.

    ignore : iterable[str] | None

        File names to skip, e.g. {"thumbs.db", ".DS_Store"}.



    Yields

    ------

    str

        Full path to each non-ignored file.

    """

    ignore = set(ignore or [])



    for dirpath, _, filenames in os.walk(root):

        for filename in filenames:

            if filename in ignore:

                continue

            yield os.path.join(dirpath, filename)