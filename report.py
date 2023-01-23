import os
import yaml

class Report(object):
    def __init__(self):
        self.kscs = list()

    def add_ksc(self, ksc):
        self.kscs.append(ksc)

    def summary(self, filename=None, overwrite=False):

        report = dict()
        for k in self.kscs:
            report[k.kernelversion] = dict()
            for ko_file in k.all_symbols_used.keys():
                ko_name = os.path.basename(ko_file)
                report[k.kernelversion][ko_name] = {'stable': len(k.get_stable_symbols(ko_file)),
                                                    'unstable': len(k.get_unstable_symbols(ko_file)),
                                                     'unknown': len(k.get_unknown_symbols(ko_file))}

        #if filename:
        #    output_filename = self.prepare_file(filename, overwrite)
        #    with open(output_filename, "a") as f:
        #        yaml.dump(report, f, default_flow_style=False)
        #print(report)
        if filename:
            self.write_yaml_file(report, filename, overwrite)
        return yaml.dump(report, default_flow_style=False)


    def full_report(self, filename=None, overwrite=True):
        """
        Save a machine readable report
        """
        report = dict()
        for k in self.kscs:
            report[k.kernelversion] = list()
            for ko_file in k.all_symbols_used.keys():
                kmod = {"name": os.path.basename(ko_file),
                        "version": k.modinfo[ko_file]['vermagic'].strip()}

                ns = list(filter(lambda x: x, k.import_ns[ko_file]))
                if len(k.import_ns[ko_file]) != 0:
                    kmod['ns'] = list(filter(lambda x: x, k.import_ns[ko_file]))

                kmod['symbols'] = {'stable': sorted(k.stable_symbols[ko_file]),
                                   #'unstable': sorted(self.nonstable_symbols_used[ko_file]),
                                   'unstable': sorted(k.nonstable_symbols_used[ko_file]),
                                   'unknown': sorted(k.nonstable_symbols_used[ko_file])}
                kmod['modifo'] = k.modinfo[ko_file].copy()
                report[k.kernelversion].append(kmod)

        if filename:
            self.write_yaml_file(report, filename, overwrite)

        return yaml.dump(report, default_flow_style=False)


    def write_yaml_file(self, report, filename, overwrite):
        output_filename = self.prepare_file(filename, overwrite)
        with open(output_filename, "a") as f:
            yaml.dump(report, f, default_flow_style=False)


    def prepare_file(self, filename, overwrite=False):
        """
        get a canonicalised text file
        """
        user_filename = os.path.expanduser(filename)
        output_filename = os.path.realpath(user_filename)
        if os.path.isfile(output_filename):

            if overwrite and os.path.isfile(output_filename):
                with open(output_filename, 'w+') as f:
                    f.truncate()

        return output_filename
