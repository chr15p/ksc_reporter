#!/usr/bin/env python3
# Copyright 2023 Red Hat Inc.
# Author: Chris Procter <cprocter@redhat.com>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.  See
# http://www.gnu.org/copyleft/gpl.html for the full text of the
# license.

"""
    a wrapper around ksc to test a kmod against arbitary kernel versions
"""

import sys
import os
import argparse
import tempfile
import shutil
import lzma

import kscreport
import kscresult
# ksc installs into a non-standard pythonpath because *sigh*
sys.path.append('/usr/share/')
sys.path.append('/usr/share/ksc')

import ksc
import utils

def main():
    """
        run the test, print the result
    """

    parser = argparse.ArgumentParser()

    parser.add_argument("-m", "--kmod", action="append", dest="kmods",
                        help="path to a kmod file", metavar="KMOD")
    parser.add_argument("--kmoddir", action="store", dest="kmoddir",
                        help="a directory containing kmods", metavar="DIR")
    parser.add_argument("-f", "--reportfile", dest="reportfile",
                        metavar="REPORTFILE", default="~/ksc-report.txt",
                        help="file to write the report to "
                             "(default ~/ksc-report.txt)")
    parser.add_argument("-d", "--releasedir", dest="releasedir",
                        help="directory containing the stablelists to use ",
                        metavar="DIR", default="/lib/modules/kabi-current/")
    parser.add_argument("-k", "--kernel", action="append", dest="kernels",
                        help="kernel version to test agains", metavar="KERNEL")
    parser.add_argument("-y", "--symverdir", dest="symverdir",
                        help="Path to kernel source directories (default /usr/src/kernels/)"
                             "(e.g. DIR/[KERNEL]/Module.symvers)",
                        metavar="DIR", default="/usr/src/kernels/")
    parser.add_argument("-o", "--overwrite",
                        action="store_true", dest="overwrite", default=False,
                        help="overwrite files without warning")
    parser.add_argument("-r", "--report",
                        action="store", dest="report", default="summary",
                        help="report type to produce (summary | full | totals | changed) ")
    parser.add_argument("-q", "--quiet",
                        action="store_true", dest="quiet", default=False,
                        help="do not write report to stdout")
    parser.add_argument("module", nargs='*',
                        help="path to a kmod file (as per the --kmod arg)", metavar="KMOD")

    options = parser.parse_args()

    # options.kmods and options.module are both paths to kmod with differnet names to keep
    # argparse happy we probably dont need the -m argument but its nicely explicit

    if options.kmods or options.module:
        (kernel_module_files, temp_dir) = extract_xz_files(options.kmods + options.module)
    elif options.kmoddir:
        files_in_dir = [os.path.join(options.kmoddir, f) for f in os.listdir(options.kmoddir)
                        if os.path.isfile(os.path.join(options.kmoddir, f))]
        (kernel_module_files, temp_dir) = extract_xz_files(files_in_dir)
    else:
        print("at least one ko file is required")
        sys.exit(1)

    if kernel_module_files == []:
        print("no valid ko files supplied")
        sys.exit(1)

    runner = KscRunner(kernel_module_files,
                       options.releasedir,
                       options.symverdir
                       )

    report = kscreport.KscReport()

    kernels = options.kernels
    if not kernels:
        kernels = [os.uname().release]

    runner.sanity_check_kmods()

    for k in kernels:
        ksc_result = runner.generate_ksc(k)
        report.add_ksc(ksc_result)

    if options.report == 'full':
        yaml = report.full_report(options.reportfile, options.overwrite)
    elif options.report == 'changed':
        yaml = report.changed(options.reportfile, options.overwrite)
    elif options.report == 'total' or options.report == 'totals':
        yaml = report.totals(options.reportfile, options.overwrite)
    else:
        yaml = report.summary(options.reportfile, options.overwrite)

    if not options.quiet:
        print(yaml)

    if temp_dir:
        shutil.rmtree(temp_dir)


def extract_xz_files(raw_ko_files):
    """
    Extract a list of xz compressed files into a temp_dir
    the caller is responsible for cleaning up the temp_dir
    args:
        raw_ko_files - list - a list of files in xz format
    returns:
        extracted_files - the full paths to the extracted files
        temp_dir - the path to the temp directory
    """
    temp_dir = None
    extracted_files = list()
    for k in raw_ko_files:
        if k[-3:] == ".ko":
            extracted_files.append(k)
        elif k[-3:] == ".xz":

            with lzma.open(k) as xzfile:
                file_content = xzfile.read()

            if temp_dir is None:
                temp_dir = tempfile.mkdtemp()
            kofile_name = temp_dir + os.sep + os.path.basename(k[:-3])

            with open(kofile_name, "wb") as kofile:
                kofile.write(file_content)

            extracted_files.append(kofile_name)
    return (extracted_files, temp_dir)


class KscRunner(ksc.Ksc):
    """
        wrapper class around the ksc utility that generates result objects
    """
    def __init__(self,
                 ko_filepath,
                 releasedir="/lib/modules/kabi-current/",
                 symverdir="/usr/src/kernels/",
                 ):
        """
            setup ksc to test
        """

        self.kernelsymvers = dict()
        self.modinfo = dict()
        super().__init__()
        self.total = None

        self.symverdir = symverdir
        self.kmods = ko_filepath
        self.releasedir = releasedir

        # override the value in utils so we can control the whitelist dir we use
        utils.WHPATH = ""

        self.find_arch(self.kmods)

        self.read_stablelists()

        for kmod_path in self.kmods:
            self.parse_ko(kmod_path, process_stablelists=True)
            self.get_modinfo(kmod_path)

        self.remove_internal_symbols()

    def sanity_check_kmods(self):
        """
            perform sanity checks on the kmods passed
            mostly that they are all compiled for the same kernel version
            if not we're going to get into a mess so just exit with an error.
        """
        last = None
        for k in self.all_symbols_used.keys():
            kmod_kernel_version = self.modinfo[k]["vermagic"].split(" ")[0]
            if last is not None and kmod_kernel_version != last:
                print("kmods are compiled for differnet kernels! %s != %s"%(
                    last, kmod_kernel_version))
                sys.exit(2)


    def generate_ksc(self, test_kernel_version):
        """
            read in the kernel symbols and generate the reresult object
        """
        if test_kernel_version not in self.kernelsymvers:
            self.kernelsymvers[test_kernel_version] = self.read_symvers(test_kernel_version)

        #all the kmods have the same vermagic or sanity_check failed
        kmod_kernel_version = self.modinfo[self.kmods[0]]["vermagic"].split(" ")[0]

        if kmod_kernel_version not in self.kernelsymvers:
            self.kernelsymvers[kmod_kernel_version] = self.read_symvers(kmod_kernel_version)

        res = kscresult.KscResult(
            test_kernel_version,
            self.kernelsymvers[test_kernel_version],
            self.kernelsymvers[kmod_kernel_version],
            self.modinfo,
            self.nonstable_symbols_used,
            self.stable_symbols
            )

        return res



    def get_modinfo(self, path):
        """
            get modinfo data for the kmod
        """
        self.modinfo[path] = dict()
        prevkey = "UNKNOWN KEY"
        try:
            out = utils.run("modinfo '%s'" % path)
            for line in out.split("\n"):
                if len(line) == 0 or line[0] == '\t':
                    continue
                if line[0] == '\t':
                    self.modinfo[path][prevkey] += line.strip()
                else:
                    data = line.split(":", 1)
                    if len(data) < 2:
                        continue
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
            print("get_modinfo failed: %s"%err)
            sys.exit(1)


    def read_symvers(self, kernelversion):
        """
            read the list of symbols in the kernel
        """
        symverfile = os.path.join(self.symverdir, kernelversion, "Module.symvers")

        result = dict()
        try:
            with open(symverfile, "r") as fptr:
                for line in fptr.readlines():
                    if line.startswith("["):
                        continue
                    fields = line.split()
                    result[fields[1]] = fields[0]
        except IOError as err:
            print(err)
            print("Missing all symbol list")
            print("Do you have the kernel-devel package installed?")
            sys.exit(1)
        return result


    def read_stablelists(self):
        """
            read in the list of stable abi symbols
        """
        self.matchdata, exists = utils.read_list(self.arch, self.releasedir, self.verbose)
        if not exists:
            print("stablelist missing")
            sys.exit(12)

        return exists


if __name__ == '__main__':
    main()
    sys.exit(0)
