# -*- coding: utf-8 -*-

"""

Created on Thu Feb 12 23:55:13 2026



@author: chodo

"""



from datasets import load_dataset



# Login using e.g. `huggingface-cli login` to access this dataset

ds = load_dataset("netop/TeleLogs")

sample16q = ds["train"]["question"][16]

print("quesiton:", len(sample16q))

sample16a = ds["train"]["answer"][16]

print("answer:", sample16a)









import random

["rock", "paper", "scissors"][random.randint(0, 2)]