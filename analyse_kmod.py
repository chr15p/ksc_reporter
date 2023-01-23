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
#import yaml
import report
import result

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
    parser.add_option("-s", "--stablelists", dest="stablelistdir",
                      help="Directory containing the stable abi symbols (default /lib/modules/)",
                      metavar="DIR",
                      default="/lib/modules/")
    parser.add_option("-n", "--name", dest="reportname",
                      help="A name for the set of kmods being reported on",
                      metavar="STRING")
    parser.add_option("-o", "--overwrite",
                      action="store_true", dest="overwrite", default=False,
                      help="overwrite files without warning")

    (options, args) = parser.parse_args(sys.argv[1:])

    if not options.ko:
        print("at least one ko file is required")
        sys.exit(1)


    factory = KscFactory(options.ko,
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

        symver_report = factory.generate_ksc(symver_file, symver_name)
        kscreport.add_ksc(symver_report)

    print(kscreport.summary(options.reportfile, options.overwrite))

    kscreport.full_report(options.reportfile, options.overwrite)



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
                            #self.modinfo[path]["parm"] = dict()
                            self.modinfo[path]["parm"] = list()

                        #self.modinfo[path]["parm"][parms[0]] = parms[1]
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


#    def get_report(self):
#        """
#        Save a machine readable report
#        """
#        yamldata=dict()
#        yamldata['summary']=list()
#        yamldata['details']=list()
#
#        #print(yaml.dump(self))
#        for ko_file in self.all_symbols_used:
#            kmod={"name": os.path.basename(ko_file),
#                  "version": self.vermagic[ko_file].strip()}
#
#            ns = list(filter(lambda x: x, self.import_ns[ko_file]))
#            if len(self.import_ns[ko_file]) !=0:
#                kmod['ns']=list(filter(lambda x: x, self.import_ns[ko_file]))
#
#            kmod['symbols'] = {'stable': sorted(self.stable_symbols[ko_file]),
#                               #'unstable': sorted(self.nonstable_symbols_used[ko_file]),
#          'unstable': [n for n in self.nonstable_symbols_used[ko_file] if n in self.total ] }
#          'unknown': [n for n in self.nonstable_symbols_used[ko_file] if n not in self.total ] }
#            kmod['modinfo']=self.modinfo[ko_file]
#
#            yamldata['summary'].append({
#                        'kmod': os.path.basename(ko_file),
#                        'results': {
#                            'stable': len(kmod['symbols']['stable']),
#                            'unstable': len(kmod['symbols']['unstable']),
#                            'unknown': len(kmod['symbols']['unknown'])
#                        }})
#            yamldata['details'].append(kmod)
#        return yamldata
#
#
#    def save_report(self, yamldata, filename, overwrite=False):
#        try:
#            output_filename = self.prepare_file(filename, overwrite)
#            with open(output_filename, "a") as f:
#                yaml.dump(yamldata, f, default_flow_style=False)
#
#            print("Report writen to %s "%output_filename)
#        except Exception as e:
#            print("Error in saving the report file at %s" % output_filename)
#            print(e)
#            sys.exit(1)


#class Result(object):
#    def __init__(self):
#        self.symvers = ""
#        self.name = ""
#
##    def get_report(self):
##        r = dict()
##        r[self.symvers] = dict()
##        for k in self.kmods.keys():
##            r[self.symvers][k] = self.kmods[k]
#
#
#    def get_report(self):
#        """
#        Save a machine readable report
#        """
#        yamldata=dict()
#        yamldata[self.symvers]=list()
#        print(yamldata)
#
#        for ko_file in self.all_symbols_used:
#            print(ko_file)
#            kmod={"name": os.path.basename(ko_file),
#                  "version": self.modinfo[ko_file]['vermagic'].strip()}
#
#            ns = list(filter(lambda x: x, self.import_ns[ko_file]))
#            if len(self.import_ns[ko_file]) !=0:
#                kmod['ns']=list(filter(lambda x: x, self.import_ns[ko_file]))
#
#            kmod['symbols'] = {'stable': sorted(self.stable_symbols[ko_file]),
#                               #'unstable': sorted(self.nonstable_symbols_used[ko_file]),
#             'unstable': [n for n in self.nonstable_symbols_used[ko_file] if n in self.total ],
#             'unknown': [n for n in self.nonstable_symbols_used[ko_file] if n not in self.total ] }
#            kmod['modinfo']=self.modinfo[ko_file]
#            #print(kmod)
#            yamldata[self.symvers].append(kmod)
#
#        #print(yamldata)
#        #print(yaml.dump(yamldata))
#        return yamldata
#
#def prepare_file(filename, overwrite=False):
#        """
#        get a canonicalised text file
#        """
#        user_filename = os.path.expanduser(filename)
#        output_filename = os.path.realpath(user_filename)
#        if os.path.isfile(output_filename):
#
#            if overwrite==True:
#                if os.path.isfile(output_filename):
#                    with open(output_filename, 'w+') as f:
#                        f.truncate()
#
#        return output_filename




if __name__ == '__main__':
    main()
    sys.exit(0)
