import os
import re
import yaml

class KscReport():
    """
    write out a report based on one or more ksc result object
    """
    def __init__(self, results=None):
        """
            create the report object
            results - list of kscresult objects
        """
        self.kscs = list()
        if results is not None:
            self.kscs += results


    def add_ksc(self, ksc_result):
        """
        add a kscresult object to the list
        """
        self.kscs.append(ksc_result)


    def report_summary_yaml(self, filename=None, overwrite=False):
        """
        generate a yaml summary report from the kscresults
        args:
          filename - string - if given write it out to that file as well as returning it
          overwrite - bool - if True truncate the file (otherwise append to it)
        """

        report = dict()
        for r in self.kscs:
            report[r.kernelversion] = dict()
            for k in r.kmods:
                name = os.path.basename(k)
                report[r.kernelversion][name] = {'stable': len(r.get_all_stable_symbols(k)),
                                                 'unstable':len(r.get_all_unstable_symbols(k)),
                                                 'unknown': len(r.get_unknown_stable_symbols(k)+
                                                                r.get_unknown_unstable_symbols(k))}
        if filename:
            self.write_yaml_file(report, filename, overwrite)
        return yaml.dump(report, default_flow_style=False)


    def report_totals_yaml(self, filename=None, overwrite=False):
        """
        generate a yaml totals report from the kscresults
        args:
          filename - string - if given write it out to that file as well as returning it
          overwrite - bool - if True truncate the file (otherwise append to it)
        """
        report = dict()
        for k in self.kscs:
            changed = 0
            unchanged = 0
            for ko_file in k.kmods:
                if len(k.get_unknown_stable_symbols(ko_file)) > 0 or \
                   len(k.get_unknown_unstable_symbols(ko_file)) > 0 or \
                   len(k.get_changed_unstable_symbols(ko_file)) > 0 or \
                   len(k.get_changed_stable_symbols(ko_file)) > 0:
                    changed += 1
                else:
                    unchanged += 1

            report[k.kernelversion] = {'changed': changed, 'unchanged': unchanged}

        if filename:
            self.write_yaml_file(report, filename, overwrite)
        return yaml.dump(report, default_flow_style=False)


    def report_totals_csv(self, filename=None, overwrite=False):
        """
        generate a yaml totals report from the kscresults
        args:
          filename - string - if given write it out to that file as well as returning it
          overwrite - bool - if True truncate the file (otherwise append to it)
        """
        report = "kernel, changed\n"
        for k in sorted(self.kscs, key=kernel_key):
            changed = 0
            for ko_file in k.kmods:
                changed += len(k.get_unknown_stable_symbols(ko_file)) +\
                          len(k.get_unknown_unstable_symbols(ko_file)) +\
                          len(k.get_changed_unstable_symbols(ko_file)) +\
                          len(k.get_changed_stable_symbols(ko_file))
            report += "%s,%s\n"%(k.kernelversion, changed)

        if filename:
            self.write_yaml_file(report, filename, overwrite)
        return report


    def report_changed_yaml(self, filename=None, overwrite=False):
        """
        generate a yaml report of how many symbols have changed in the kernel
        args:
          filename - string - f given write it out to that file as well as returning it
          overwrite - bool - if True truncate the file (otherwise append to it)
        """
        report = dict()
        for k in self.kscs:
            report[k.kernelversion] = dict()
            for ko_file in k.kmods:
                ko_name = os.path.basename(ko_file)
                report[k.kernelversion][ko_name] = {
                    'stable': {'unchanged': len(k.get_unchanged_stable_symbols(ko_file)),
                               'changed': len(k.get_changed_stable_symbols(ko_file))},
                    'unstable': {'unchanged': len(k.get_unchanged_unstable_symbols(ko_file)),
                                 'changed': len(k.get_changed_unstable_symbols(ko_file))},
                    'unknown': len(k.get_unknown_stable_symbols(ko_file)
                                   +k.get_unknown_stable_symbols(ko_file))}

        if filename:
            self.write_yaml_file(report, filename, overwrite)
        return yaml.dump(report, default_flow_style=False)


    def report_full_yaml(self, filename=None, overwrite=True):
        """
        generate a full yaml report of all the symbols used by the kmod classified by
        if they are stable/unstable/unknown and if they have changed or not between the i
        compiled for kernel and the tested against kernel
        args:
          filename - string - f given write it out to that file as well as returning it
          overwrite - bool - if True truncate the file (otherwise append to it)
        """
        report = dict()
        for k in self.kscs:
            report[k.kernelversion] = dict()
            #report[k.kernelversion] = list()
            for ko_file in k.kmods:
                kmod = {"kmod_name": os.path.basename(ko_file),
                        "version": k.modinfo[ko_file]['vermagic'].strip()}

                if 'import_ns' in k.modinfo[ko_file].keys():
                    kmod['ns'] = list(filter(lambda x: x, k.modinfo[ko_file]['import_ns']))

                kmod['symbols'] = {
                    'stable': {'unchanged': sorted(k.get_unchanged_stable_symbols(ko_file)),
                               'changed': sorted(k.get_changed_stable_symbols(ko_file))},
                    'unstable': {'unchanged': sorted(k.get_unchanged_unstable_symbols(ko_file)),
                                 'changed': sorted(k.get_changed_unstable_symbols(ko_file))},
                    'unknown': sorted(k.get_unknown_stable_symbols(ko_file)
                                      +k.get_unknown_stable_symbols(ko_file))}

                kmod['modinfo'] = k.modinfo[ko_file].copy()
                report[k.kernelversion][os.path.basename(ko_file)] = kmod
                #report[k.kernelversion].append(kmod)

        if filename:
            self.write_yaml_file(report, filename, overwrite)

        return yaml.dump(report, default_flow_style=False)

    def write_file(self, report, filename, overwrite):
        output_filename = self.prepare_file(filename, overwrite)
        with open(output_filename, "a") as f:
            f.write(report)


    def write_yaml_file(self, report, filename, overwrite):
        """
        write out the report struct as yaml
        """
        output_filename = self.prepare_file(filename, overwrite)
        with open(output_filename, "a") as f:
            yaml.dump(report, f, default_flow_style=False)


    def prepare_file(self, filename, overwrite=False):
        """
        get a canonicalised text file from teh filename
        args:
          filename - string - the name to canonicalise
          overwrite - bool - if true then truncate any exisitng file with that name
        """
        user_filename = os.path.expanduser(filename)
        output_filename = os.path.realpath(user_filename)
        if os.path.isfile(output_filename):

            if overwrite and os.path.isfile(output_filename):
                with open(output_filename, 'w+') as f:
                    f.truncate()

        return output_filename




def kernel_key(kernel):
    """
        turn a kernel version into a string that can then be sorted on
    """
    version = re.split(r'[\.\-]', kernel.kernelversion)
    vlen = len(version)-2
    string = ""
    for i in range(0, 6):
        if i < vlen:
            string += version[i].rjust(3, '0')
        else:
            string += '000'

    return string
