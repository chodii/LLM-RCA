# -*- coding: utf-8 -*-

"""

Created on Mon Feb 23 02:12:11 2026



@author: chodo

"""



import os

from pathlib import Path



def _depth(p: str) -> int:

    # normalize and count path parts robustly

    return len(Path(p).resolve().parts)



def _basename(p: str) -> str:

    p = str(Path(p))

    name = os.path.basename(p.rstrip("\\/"))

    return name if name else p  # for drive roots etc.



def _cat_label(cats) -> str:

    if not cats:

        return "{}"

    return "{" + ",".join(sorted(cats)) + "}"



def write_tree_dot(levels: dict[int, dict[str, set[str]]], out_dot: str = "tree.dot"):

    """

    levels: { level_int : { folder_path : set(categories) } }

    Writes Graphviz DOT representing the tree across levels.

    """

    # Collect all nodes from all levels

    nodes = {}

    for lvl, mp in levels.items():

        for path, cats in mp.items():

            nodes[path] = cats



    # Build edges only between adjacent levels

    edges = set()

    level_keys = sorted(levels.keys())

    for i in range(len(level_keys) - 1):

        a = level_keys[i]

        b = level_keys[i + 1]

        parents = list(levels[a].keys())

        children = list(levels[b].keys())



        # Index parents by their normalized prefix for faster matching

        # We'll match child to the *closest* parent (deepest) among level a.

        for ch in children:

            ch_norm = str(Path(ch))

            best_parent = None

            best_depth = -1

            for pa in parents:

                pa_norm = str(Path(pa))

                # child must be under parent

                # use commonpath to avoid simple string prefix bugs

                try:

                    common = os.path.commonpath([pa_norm, ch_norm])

                except ValueError:

                    continue  # different drives on Windows

                if common == pa_norm:

                    d = _depth(pa_norm)

                    if d > best_depth:

                        best_parent = pa_norm

                        best_depth = d

            if best_parent is not None:

                edges.add((best_parent, ch_norm))



    # Emit DOT

    def node_id(p: str) -> str:

        # Stable unique id (Graphviz identifiers can't contain backslashes nicely)

        # Use a hash-like safe id from the path

        return "n" + str(abs(hash(p)))



    with open(out_dot, "w", encoding="utf-8") as f:

        f.write("digraph G {\n")

        f.write('  rankdir="TB";\n')

        f.write('  node [shape=box, fontname="Consolas"];\n')

        f.write('  edge [arrowhead=none];\n\n')



        # nodes

        for path, cats in nodes.items():

            label = f"{_basename(path)}\\n{_cat_label(cats)}"

            f.write(f'  {node_id(path)} [label="{label}"];\n')



        f.write("\n")

        # edges

        for pa, ch in sorted(edges, key=lambda x: (x[0], x[1])):

            f.write(f"  {node_id(pa)} -> {node_id(ch)};\n")



        f.write("}\n")



    print(f"Wrote: {out_dot}")

    print("Render e.g.:  dot -Tpng tree.dot -o tree.png")

    print("Or:           dot -Tsvg tree.dot -o tree.svg")