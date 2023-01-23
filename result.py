"""
    result of ksc run
"""
import os.path

class Result():
    """
        a set of results from ksc that can generate reports
    """
    def __init__(self,
                 kernelversion,
                 symvers,
                 total,
                 modinfo,
                 nonstable_symbols_used,
                 import_ns,
                 stable_symbols,
                 all_symbols_used):

        """
            setup the object
        """
        self.kernelversion = kernelversion
        if kernelversion is None:
            self.kernelversion = os.path.dirname(symvers)

        self.symvers = symvers
        self.total = total
        self.modinfo = modinfo
        self.nonstable_symbols_used = nonstable_symbols_used
        self.import_ns = import_ns
        self.stable_symbols = stable_symbols
        self.all_symbols_used = all_symbols_used

        self._stable_symbols = None
        self._unstable_symbols = None
        self._unknown_symbols = None

    def get_kmods(self):
        """
            get the list of kmods tested
        """
        self.all_symbols_used.keys()

    def get_stable_symbols(self, ko_file):
        """
            get the symbols used that are in the Red Hat whitelist (and so ca bre relied on
        """
        if not self._stable_symbols:
            self._stable_symbols = sorted(self.stable_symbols[ko_file])
        return self._stable_symbols


    def get_unstable_symbols(self, ko_file):
        """
            get the symbols used that are not inthe Red Hat whitelist
        """
        if not self._unstable_symbols:
            self._unstable_symbols = [n for n in self.nonstable_symbols_used[ko_file]
                                      if n in self.total]
        return self._unstable_symbols


    def get_unknown_symbols(self, ko_file):
        """
            get the symbols that are not in the kernel version we're testing
        """
        if not self._unknown_symbols:
            self._unknown_symbols = [n for n in self.nonstable_symbols_used[ko_file]
                                     if n not in self.total]
        return self._unknown_symbols
