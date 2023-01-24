#!/usr/bin/env python3
# Copyright 2023 Red Hat Inc.
# Author: Chris Procter <cprocter@redhat.com>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.  See
# http://www.gnu.org/copyleft/gpl.html for the full text of the
# license.



import sys
import os
from optparse import OptionParser
import report
import result
import lzma
import tempfile
import shutil

# ksc installs into a non-standard pythonpath because *sigh*
sys.path.append('/usr/share/')
sys.path.append('/usr/share/ksc')

import ksc
import utils

def main():
    """
        run the test, peint the result
    """
    parser = OptionParser()
    parser.add_option("-k", "--ko", action="append", dest="ko",
                      help="path to the ko file", metavar="KO")
    parser.add_option("-f", "--reportfile", dest="reportfile",
                      metavar="REPORTFILE", default="~/ksc-report.txt",
                      help="file to write the report to "
                           "(default ~/ksc-report.txt)")
    parser.add_option("-d", "--releasedir", dest="releasedir",
                      help="directory containing the stablelists to use "
                           "(calculated from -s and -r if not given) ",
                      metavar="DIR")
    parser.add_option("-r", "--release", dest="release",
                      help="RHEL release to compare for stablelist, e.g. 8.7"
                           "(default current)", metavar="RELEASE")
    parser.add_option("-y", "--symvers", dest="symvers", action="append",
                      help="Path to a Module.symvers file."
                           "Current kernel path is used if not specified.",
                      metavar="SYMVERS")
    parser.add_option("-w", "--stablelists", dest="stablelistdir",
                      help="Directory containing the stable abi symbols (default /lib/modules/)",
                      metavar="DIR",
                      default="/lib/modules/")
    parser.add_option("-n", "--name", dest="reportname",
                      help="A name for the set of kmods being reported on",
                      metavar="STRING")
    parser.add_option("-o", "--overwrite",
                      action="store_true", dest="overwrite", default=False,
                      help="overwrite files without warning")
    parser.add_option("-s", "--summary",
                      action="store_true", dest="summary", default=False,
                      help="produce a summary report")
    parser.add_option("-q", "--quiet",
                      action="store_true", dest="quiet", default=False,
                      help="do not write report to stdout")

    (options, args) = parser.parse_args(sys.argv[1:])

    if not options.ko:
        print("at least one ko file is required")
        sys.exit(1)

    (kernelModuleFiles, temp_dir)  = extract_xz_files(options.ko)
    factory = KscFactory(kernelModuleFiles,
                         options.releasedir,
                         options.release,
                         options.stablelistdir,
                         )

    kscreport = report.Report()


    for i in options.symvers:
        symver_parts = i.split(":", 1)
        symver_file = symver_parts[0]
        if len(symver_parts) == 2:
            symver_name = symver_parts[1]
        else:
            symver_name = os.path.dirname(symver_parts[0])
            symver_name = os.path.basename(symver_name)

        symver_result = factory.generate_ksc(symver_file, symver_name)
        kscreport.add_ksc(symver_result)

    if options.summary:
        if options.quiet:
            kscreport.summary(options.reportfile, options.overwrite)
        else:
            print(kscreport.summary(options.reportfile, options.overwrite))
    else:
        if options.quiet:
            kscreport.full_report(options.reportfile, options.overwrite)
        else:
            print(kscreport.full_report(options.reportfile, options.overwrite))

    if temp_dir:
        shutil.rmtree(temp_dir)


def extract_xz_files(raw_ko_files):
    temp_dir = None
    kernelModuleFiles = list()
    for k in raw_ko_files:
        if k[-3:] == ".ko":
            kernelModuleFiles.append(k)
        elif k[-3:] == ".xz":

            with lzma.open(k) as xzfile:
                file_content = xzfile.read()

            if temp_dir == None:
                temp_dir = tempfile.mkdtemp()
            kofile_name = temp_dir + os.sep + os.path.basename(k[:-3])

            with open(kofile_name, "wb") as kofile:
                kofile.write(file_content)
                print(kofile_name)

            kernelModuleFiles.append(kofile_name)
    return (kernelModuleFiles, temp_dir)

class KscFactory(ksc.Ksc):
    """
        wrapper class around the ksc utility that generates result objects
    """
    def __init__(self,
                 ko_filepath,
                 releasedir=None,
                 release=None,
                 stablelistdir="/lib/modules/",
                 ):
        """
        """

        self.modinfo = dict()
        super().__init__()
        self.total = None

        self.stablelist = stablelistdir
        self.ko = ko_filepath
        self.releasedir = self.get_releasedir(releasedir, stablelistdir, release)

        # override the value in utils so we can control the whitelist dir we use
        utils.WHPATH = ""

        self.find_arch(self.ko)

        self.read_stablelists()

        for kmod_path in self.ko:
            self.parse_ko(kmod_path, process_stablelists=True)
            self.get_modinfo(kmod_path)

        self.remove_internal_symbols()


    def generate_ksc(self, symvers, name):
        """
            read in the kernel symbols and generate the reresult object
        """
        self.read_symvers(symvers)
        res = result.Result(
            name,
            symvers,
            self.total,
            self.modinfo,
            self.nonstable_symbols_used,
            self.import_ns,
            self.stable_symbols,
            self.all_symbols_used
            )

        return res


    def get_releasedir(self, releasedir, stablelistdir, release):
        """
            get the directory containing the stable abi list file
        """
        if releasedir:
            return releasedir

        if release:
            return os.path.join(stablelistdir, 'kabi-rhel' + release.replace('.', ''))

        return os.path.join(stablelistdir, 'kabi-current')


    def get_modinfo(self, path):
        """
            get modinfo data for the kmod
        """
        self.modinfo[path] = dict()
        prevkey = "UNKNOWN KEY"
        try:
            out = utils.run("modinfo '%s'" % path)
            for line in out.split("\n"):
                if len(line) == 0:
                    continue
                if line[0] == '\t':
                    self.modinfo[path][prevkey] += line.strip()
                else:
                    data = line.split(":", 1)
                    if data[0] == "parm":
                        parms = data[1].strip().split(":", 1)
                        if "parm" not in self.modinfo[path]:
                            self.modinfo[path]["parm"] = list()

                        self.modinfo[path]["parm"].append({'name': parms[0],
                                                           'description':parms[1]})
                    else:
                        self.modinfo[path][data[0]] = data[1].strip()
                    prevkey = data[0]
        except Exception as err:
            print(err)
            sys.exit(1)


    def read_symvers(self, symverfile):
        """
            read the list of symbols in the kernel
        """
        self.total = utils.read_total_list(symverfile)


    def read_stablelists(self):
        """
            read in the lisy of stable abi symbols
        """
        self.matchdata, exists = utils.read_list(self.arch, self.releasedir, self.verbose)
        if not exists:
            print("stablelist missing")
            sys.exit(12)

        return exists


if __name__ == '__main__':
    main()
    sys.exit(0)
