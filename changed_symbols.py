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

def kernel_key(k):
    x = re.split('[\.\-]',k)
    l = len(x) 
    string=""
    for i in range(0, l):
        string +=x[i].rjust(3,'0')

    return string

def get_filenames(kernellist, symverdir=None):
    dirlist = dict()
    filelist = list()
    if symverdir:
        if symverdir[-1] != '/':
            symverdir += '/'
        offset = len(symverdir)
    else:
        offset=0

    for f in kernellist:
        if offset != 0 and f[0:offset] == symverdir:
            strict_ver = re.sub(r'\.el.*\.x86_64$',"", f[offset:]).replace('-','.')
            dirlist[strict_ver] = f[offset:]
        else:
            strict_ver = re.sub(r'\.el.*\.x86_64$',"", f).replace('-','.')
            dirlist[strict_ver] = f
                    
    sorteddirlist= sorted(dirlist,key=kernel_key)
    for k in sorteddirlist:
        filelist.append(dirlist[k])
#sys.exit(0)

    return filelist

def get_y_version(kernel):
    x = re.split('[\.\-]',kernel)
    return x[0]+"."+x[1]+"."+x[2]+"-"+x[3]+".el8.x86_64"

parser = argparse.ArgumentParser()

parser.add_argument("-b","--basekernel", action="store", dest="basekernel", default=None,
                    help="a kernel version to compare all others to", metavar="KVER")
parser.add_argument("-k","--kerneldir", action="store", dest="kerneldir",
                    help="a directory containing kernels to compare", metavar="DIR")
parser.add_argument("-w", "--whitelist", dest="whitelist",
                    help="file containing the whitelist to use ",
                    metavar="FILE", default="/lib/modules/kabi-current/kabi_stablelist_x86_64")
parser.add_argument("kernel", nargs='*',
                    help="a kernel version within kerneldir", metavar="KERNEL")
options = parser.parse_args()

if len(sys.argv) == 1:
    parser.print_help(sys.stderr)
    sys.exit(0)

if options.kernel and len(options.kernel)< 2:
    print("if any kernel args are given then at least 2 specified")
    sys.exit(0)

if options.kerneldir:
    kerneldir = options.kerneldir
else:
    if options.kernel:
        kerneldir = os.path.dirname(options.kernel[0])
    else:
        kerneldir="./kernels"

filelist = list()
if options.basekernel:
    filelist.append(options.basekernel)

if options.kernel:
    kernellist = options.kernel
else:
    kernellist = os.listdir(kerneldir)

filelist += get_filenames(kernellist, kerneldir)
whitelist = read_whitelist(options.whitelist)

print("%-30s,%-30s,%-6s,%s"%("From","To", "stable", "unstable"))
for i in range(1,len(filelist)):
    if options.basekernel:
        kernel1= filelist[0]
    else:
        kernel1= filelist[i-1]
    kernel2 = filelist[i]
    file1= read_symvers(kerneldir, kernel1)

    file2= read_symvers(kerneldir, kernel2)
    stable=0
    unstable=0
    for k,v in file1.items():
    	if k not in file2 or file2[k] != v:
                if k not in whitelist:
                    unstable+=1
                else:
                    stable+=1
      
    print("%-30s,%-30s,%-6d,%d"%(kernel1, kernel2, stable, unstable))
