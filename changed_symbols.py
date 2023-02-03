#!/usr/bin/env python3

# Copyright 2023 Red Hat Inc.
# Author: Chris Procter <cprocter@redhat.com>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.  See
# http://www.gnu.org/copyleft/gpl.html for the full text of the
# license.

import os
import sys
import re
import argparse

def read_whitelist(fpath):
    """
        read the whitelist file
        returns a list of the symbols in the whitelist
    """
    result = []
    try:
        #print("Reading %s" % fpath)
        fptr = open(fpath)
        for line in fptr.readlines():
            if line.startswith("["):
                continue
            result.append(line.strip("\n\t"))
        fptr.close()
    except IOError as err:  # pragma: no cover
        print(err)
        print("failed reading stablelist")

    return result, True


def read_symvers(symverdir, kernelversion):
    """
	read the list of symbols in the kernel
    """
    symverfile = os.path.join(symverdir, kernelversion, "Module.symvers")

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

def kernel_key(kernel):
    """
        turn a kernel version into a string that can then be sorted on
    """
    version = re.split(r'[\.\-]', kernel)
    l = len(version)
    string = ""
    for i in range(0, l):
        string += version[i].rjust(3, '0')

    return string

def sort_kernel_directorys(kernellist, symverdir=None):
    """
        produce a sorted list of the kernel directories
        we're expecting to be passed a list of $DIR/$KERNEL paths
        and for each for a $DIR/$KERNEL/Module.symvers file to exist
        this sorts that list on the $KERNEL part
    """
    dirlist = dict()
    filelist = list()
    if symverdir:
        if symverdir[-1] != '/':
            symverdir += '/'
        offset = len(symverdir)
    else:
        offset = 0

    for f in kernellist:
        if offset != 0 and f[0:offset] == symverdir:
            strict_ver = re.sub(r'\.el.*\.x86_64$', "", f[offset:]).replace('-', '.')
            dirlist[strict_ver] = f[offset:]
        else:
            strict_ver = re.sub(r'\.el.*\.x86_64$', "", f).replace('-', '.')
            dirlist[strict_ver] = f

    sorteddirlist = sorted(dirlist, key=kernel_key)
    for k in sorteddirlist:
        filelist.append(dirlist[k])

    return filelist


parser = argparse.ArgumentParser()

parser.add_argument("-b", "--basekernel", action="store", dest="basekernel", default=None,
                    help="a kernel version to compare all others to", metavar="KVER")
parser.add_argument("-k", "--kerneldir", action="store", dest="kerneldir",
                    help="a directory containing kernels to compare", metavar="DIR")
parser.add_argument("-w", "--whitelist", dest="whitelist",
                    help="file containing the whitelist to use ",
                    metavar="FILE", default="/lib/modules/kabi-current/kabi_stablelist_x86_64")
parser.add_argument("-q", "--quiet", action="store_true", dest="quiet",
                    help="do not print headers")
parser.add_argument("kernel", nargs='*',
                    help="a kernel version within kerneldir", metavar="KERNEL")
options = parser.parse_args()

if len(sys.argv) == 1:
    parser.print_help(sys.stderr)
    sys.exit(0)

if options.kernel and len(options.kernel) < 2:
    print("if any kernel args are given then at least 2 specified")
    sys.exit(0)

if options.kerneldir:
    KERNELDIR = options.kerneldir
else:
    if options.kernel:
        KERNELDIR = os.path.dirname(options.kernel[0])
    else:
        KERNELDIR = "./kernels"

sorted_kernels = list()
if options.basekernel:
    sorted_kernels.append(options.basekernel)

if options.kernel:
    KERNEL_LIST = options.kernel
else:
    KERNEL_LIST = os.listdir(KERNELDIR)

sorted_kernels += sort_kernel_directorys(KERNEL_LIST, KERNELDIR)
WHITELIST = read_whitelist(options.whitelist)

if not options.quiet:
    print("%-30s,%-30s,%-6s,%s"%("From", "To", "stable", "unstable"))

for i in range(1, len(sorted_kernels)):
    if options.basekernel:
        kernel1 = sorted_kernels[0]
    else:
        kernel1 = sorted_kernels[i-1]
    kernel2 = sorted_kernels[i]

    ## really ought to cache these so we dont keep rereading the same file
    file1 = read_symvers(KERNELDIR, kernel1)

    file2 = read_symvers(KERNELDIR, kernel2)
    stable = 0
    unstable = 0
    for k, v in file1.items():
        if k not in file2 or file2[k] != v:
            if k not in WHITELIST:
                unstable += 1
            else:
                stable += 1

    print("%-30s,%-30s,%-6d,%d"%(kernel1, kernel2, stable, unstable))
