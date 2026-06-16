# -*- coding: utf-8 -*-

"""

Created on Thu Feb 19 16:58:50 2026



@author: chodo

"""



from rca.data_preprocessing import _dataset_walker



import os

from pathlib import Path



def get_DES_filter():

    acceptable_file_formats = {"docx":"docx"

                               , "txt":"txt"

                               , "log":"log"

                               , "status":"status"

                               , "stderr":"stderr"

                               , None:None

                               , "bin":"bin"

                               , "pdf":"pdf"

                               }

    return File_Filter(accepted_file_formats=acceptable_file_formats)



class File_Filter:

    def __init__(self, accepted_file_formats={}):

        self.accepted_file_formats = accepted_file_formats

        self.ERROR = -1

        self.NONE = "None"

        self.errors = 0

    

    def _update_ff(self, whitelist=None, blacklist=None):

        if whitelist is not None:

            for k in whitelist:

                if k not in self.accepted_file_formats:

                    self.accepted_file_formats[k] = whitelist[k]

        if blacklist is not None:

            for k in blacklist:

                if k in self.accepted_file_formats:

                    self.accepted_file_formats.pop(k)

                    

    def _classify(self, fp):

        for suffix in _dataset_walker.parse_suffixes(fp):

            if suffix is None:

                suffix = self.NONE

            if suffix in self.accepted_file_formats:

                return self.accepted_file_formats[suffix]

        return self.ERROR

    

    def filter_dataset(self, root, whitelist=None, blacklist=None):

        self._update_ff(whitelist=whitelist, blacklist=blacklist)

        for fp in _dataset_walker.dataset_iterator(root=root):

            classification = self._classify(fp)

            if classification == self.ERROR:

                self.errors += 1

                continue

            yield fp, classification

        if self.errors >= 1:

            print("File_Filter failed to yield:",self.errors, "files")

            