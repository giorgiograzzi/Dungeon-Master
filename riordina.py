#!/usr/bin/env python3
"""Sposta i file 'piatti' nelle cartelle giuste: a__b__c.ext -> a/b/c.ext
(i PDF lasciati nella radice vanno in docs/srd/). Si può rilanciare senza danni."""
import os
import shutil

root = os.path.dirname(os.path.abspath(__file__))
me = os.path.basename(__file__)
moved = 0
for name in sorted(os.listdir(root)):
    src = os.path.join(root, name)
    if not os.path.isfile(src) or name == me:
        continue
    if "__" in name and not name.startswith("__"):
        dest = os.path.join(root, *name.split("__"))
    elif name.lower().endswith(".pdf"):
        dest = os.path.join(root, "docs", "srd", name)
    else:
        continue
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.move(src, dest)
    moved += 1
    print("spostato:", name, "->", os.path.relpath(dest, root))
print(f"Fatto: {moved} file sistemati.")
