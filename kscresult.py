"""
    result of ksc run
"""
class KscResult():
    """
        a set of results from ksc that can generate reports
        kernelversion - the kernel ersion to test (e.g. 4.18.0-425.3.1.el8.x86_64)
        symvers_tested - dict - the symbols(key) and crc (value) of all the symbols
                                in the kernel to test against
        symvers_compiled - dict - the symbol versions in the lernelthe kmod is compiled against
        modinfo - dict - the output of modinfo [kmod] as a dict
        nonstable_symbols_used - dict - the symbols used in the kmod (key)
                                        not in the whitelist as a list(value)
        stable_symbols_used - dict - the symbols used in the kmod (key)
                                     that are in the whitelist as a list(value)
        kmods - list - the kmods used
    """
    def __init__(self,
                 kernelversion,
                 symvers_tested,
                 symvers_compiled,
                 modinfo,
                 nonstable_symbols_used,
                 stable_symbols_used):

        """
            setup the object
        """
        self.kernelversion = kernelversion
        self.symvers_tested = symvers_tested
        self.symvers_compiled = symvers_compiled
        self.modinfo = modinfo
        self.nonstable_symbols_used = nonstable_symbols_used
        self.stable_symbols_used = stable_symbols_used
        ## not clear if we want/need this so leaving it here for future reference
        ## self.import_ns = modinfo['import_ns']

        self.total = symvers_tested.keys()
        self.kmods = nonstable_symbols_used.keys()

        self._stable_symbols = dict()
        self._unstable_symbols = dict()
        self._changed_symbols = dict()
        self._unchanged_symbols = dict()

        #self._stable_symbols_all = dict()
        #self._unstable_symbols_all = dict()
        #self._unknown_symbols_all = dict()

    def get_kmods(self):
        """
            get the list of kmods tested
        """
        return self.kmods


#    def get_stable_symbols(self, ko_file):
#        """
#            get the symbols used that are in the Red Hat whitelist (and so can be relied on)
#        """
#        if ko_file not in self._stable_symbols_all.keys():
#            self._stable_symbols_all[ko_file] = sorted(self.stable_symbols_used[ko_file])
#        return self._stable_symbols_all[ko_file]
#
#
#    def get_unstable_symbols(self, ko_file):
#        """
#            get the symbols used that are not in the Red Hat whitelist
#        """
#        if ko_file not in self._unstable_symbols_all.keys():
#            self._unstable_symbols_all[ko_file] = [n for n in self.nonstable_symbols_used[ko_file]
#                                                   if n in self.total]
#        return self._unstable_symbols_all[ko_file]
#
#    def get_unknown_symbols(self, ko_file):
#        """
#            get the symbols that are not in the kernel version we're testing
#        """
#        if ko_file not in self._unknown_symbols_all.keys():
#            self._unknown_symbols_all[ko_file] = [n for n in self.nonstable_symbols_used[ko_file]
#                                                  if n not in self.total]
#        return self._unknown_symbols_all[ko_file]
#

    def classify_unstable_symbols(self, ko_file):
        """
            sort the unstable (non-whitelisted) symbols used for a kmod
            based on whether they have changed since the kernel version the
            kmod was built for
            ko_file - string - the path to the kmod to be sorted
        """
        if ko_file not in self._unstable_symbols.keys():
            self._unstable_symbols[ko_file] = {'all': list(),
                                               'changed': list(),
                                               'unchanged': list(),
                                               'unknown': list(),
                                               }

            for s in self.nonstable_symbols_used[ko_file]:
                if s in self.total:
                    self._unstable_symbols[ko_file]['all'].append(s)

                if s not in self.symvers_tested:
                    self._unstable_symbols[ko_file]['unknown'].append(s)
                elif self.symvers_tested[s] != self.symvers_compiled[s]:
                    self._unstable_symbols[ko_file]['changed'].append(s)
                else:
                    self._unstable_symbols[ko_file]['unchanged'].append(s)

        return self._unstable_symbols[ko_file]


    def get_all_unstable_symbols(self, ko_file):
        """
        get all the unstable symbols used in this kmod
        """
        if ko_file not in self._unstable_symbols.keys():
            self.classify_unstable_symbols(ko_file)
        return  self._unstable_symbols[ko_file]['all']

    def get_changed_unstable_symbols(self, ko_file):
        """
        get all the unstable symbols used in this kmod
        that have changed between the compiled and the tested against kernel
        """
        if ko_file not in self._unstable_symbols.keys():
            self.classify_unstable_symbols(ko_file)
        return  self._unstable_symbols[ko_file]['changed']

    def get_unchanged_unstable_symbols(self, ko_file):
        """
        get all the unstable symbols used in this kmod
        that have not changed between the compiled and the tested against kernel
        """
        if ko_file not in self._unstable_symbols.keys():
            self.classify_unstable_symbols(ko_file)
        return  self._unstable_symbols[ko_file]['unchanged']

    def get_unknown_unstable_symbols(self, ko_file):
        """
        get all the unstable symbols used in this kmod
        that do not exist in the tested against kernel
        """
        if ko_file not in self._unstable_symbols.keys():
            self.classify_unstable_symbols(ko_file)
        return  self._unstable_symbols[ko_file]['unknown']

    def classify_stable_symbols(self, ko_file):
        """
            sort the stable (whitelisted) symbols used for a kmod
            based on whether they have changed since the kernel version the
            kmod was built for
            ko_file - string - the path to the kmod to be sorted
        """
        if ko_file not in self._stable_symbols.keys():
            self._stable_symbols[ko_file] = {'all': list(),
                                             'changed': list(),
                                             'unchanged': list(),
                                             'unknown': list(),
                                            }

            for s in self.stable_symbols_used[ko_file]:
                if s in self.total:
                    self._stable_symbols[ko_file]['all'].append(s)

                if s not in self.symvers_tested:
                    self._stable_symbols[ko_file]['unknown'].append(s)
                elif self.symvers_tested[s] != self.symvers_compiled[s]:
                    self._stable_symbols[ko_file]['changed'].append(s)
                else:
                    self._stable_symbols[ko_file]['unchanged'].append(s)

        return self._stable_symbols[ko_file]


    def get_all_stable_symbols(self, ko_file):
        """
        get all the stable symbols used in this kmod
        """
        if ko_file not in self._stable_symbols.keys():
            self.classify_stable_symbols(ko_file)
        return  self._stable_symbols[ko_file]['all']

    def get_changed_stable_symbols(self, ko_file):
        """
        get all the stable (whitelisted) symbols used in this kmod
        that have changed between the compiled and the tested against kernel
        this *should* return an empty list because thats the point of the stablelist...
        unless you are testing a kmod compiled for a different major RHEL version
        """
        if ko_file not in self._stable_symbols.keys():
            self.classify_stable_symbols(ko_file)
        return  self._stable_symbols[ko_file]['changed']

    def get_unchanged_stable_symbols(self, ko_file):
        """
        get all the stable (whitelisted) symbols used in this kmod
        that have not changed between the compiled and the tested against kernel
        """
        if ko_file not in self._stable_symbols.keys():
            self.classify_stable_symbols(ko_file)
        return  self._stable_symbols[ko_file]['unchanged']

    def get_unknown_stable_symbols(self, ko_file):
        """
        get all the stable (whitelisted) symbols used in this kmod
        that do not exist in the tested against kernel
        again this *should be* an empty list unless testing between major RHEL versions
        """
        if ko_file not in self._stable_symbols.keys():
            self.classify_stable_symbols(ko_file)
        return  self._stable_symbols[ko_file]['unknown']
