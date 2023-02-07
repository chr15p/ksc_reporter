### Descriptions
This script returns yaml formatted reports on the symbols used by a kernel module and whether they conform to the RHEL list of stable symbols (i.e. those whos usage remains the same across all minor versions of a RHEL release) and which are not available in a given kernel version. It acts as a wrapper around the ksc tool.

Multiple kernel modules can be passed in which case symbols will be checked between them and anything required by one kmod but provided by another in the set is regarded as a met dependancy and not reported.

ksc itself has the ability to report the use of unstable kernel symgbols to bugzilla, ksc_reporter does NOT do this. 

### Requirements

This script relies on having the Red Hat kernel abi stablelist available (the kernel-abi-stablelists package) and the kernel-devel packages for both the version of the kernel the kmods were compiled against, and any kernel versions you wish to test against.

```
dnf install kernel-abi-stablelists kernel-devel
```

### help
```
~# ./ksc_reporter.py -h
usage: ksc_reporter.py [-h] [-m KMOD] [--kmoddir DIR] [-f REPORTFILE] [-d DIR]
                       [-k KERNEL] [-y DIR] [-o] [-r REPORT] [-q]
                       [KMOD [KMOD ...]]

positional arguments:
  KMOD                  path to a kmod file (as per the --kmod arg)

optional arguments:
  -h, --help            show this help message and exit
  -m KMOD, --kmod KMOD  path to a kmod file
  --kmoddir DIR         a directory containing kmods
  -f REPORTFILE, --reportfile REPORTFILE
                        file to write the report to (default ~/ksc-report.txt)
  -d DIR, --releasedir DIR
                        directory containing the stablelists to use
  -k KERNEL, --kernel KERNEL
                        kernel version to test agains
  -y DIR, --symverdir DIR
                        Path to kernel source directories (default
                        /usr/src/kernels/)(e.g. DIR/[KERNEL]/Module.symvers)
  -o, --overwrite       overwrite files without warning
  -r REPORT, --report REPORT
                        report type to produce (summary | full | totals |
                        changed)
  -q, --quiet           do not write report to stdout

```

### Example usage
```
~# ./ksc_reporter.py -m ../simple-kmod/simple-procfs-kmod.ko -f ./ksc_report.txt -d /lib/modules/kabi-current/ -k 4.18.0-425.3.1.el8.x86_64 -k 4.18.0-372.32.1.el8_6.x86_64  -y /usr/src/kernels/  ../simple-kmod/simple-kmod.ko -r summary

4.18.0-372.32.1.el8_6.x86_64:
  simple-kmod.ko:
    stable:
      changed: 0
      unchanged: 2
    unknown: 0
    unstable:
      changed: 0
      unchanged: 0
  simple-procfs-kmod.ko:
    stable:
      changed: 0
      unchanged: 11
    unknown: 0
    unstable:
      changed: 0
      unchanged: 2
4.18.0-425.3.1.el8.x86_64:
  simple-kmod.ko:
    stable:
      changed: 0
      unchanged: 2
    unknown: 0
    unstable:
      changed: 0
      unchanged: 0
  simple-procfs-kmod.ko:
    stable:
      changed: 0
      unchanged: 11
    unknown: 0
    unstable:
      changed: 0
      unchanged: 2
```

- stable symbols are those that Red Hat will maintain as stable across a major release of RHEL (i.e. RHEL8 or RHEL 9) see ()[https://access.redhat.com/solutions/444773] for more details.
- unstable symbols are symbols available in that kernel version but not covered by ABI stability.
- unknown symbols are symbols the kernel module relies upon but are not available in that version of the kernel (these will cause modprobe/insmod to fail)


- Changed symbols are those whose crc sums have changed between the version of the kernel the kmod was compiled for and the version tested against. (these are a red flag, their behaviour may have changed leading to unpredictable results)
- Unchanged symbols are those whose crc sums remain unchanged between the version of the kernel the kmod was compiled for and the version tested against. (these should probably work in teh new kernel)


Without the `-s` option a full list of the kmod info and symbols used will be produced. This can get very long for non-trivial kmods.

```
~# ./ksc_reporter.py -m ../simple-kmod/simple-procfs-kmod.ko -f ./ksc_report.txt -d /lib/modules/kabi-current/ -k 4.18.0-372.32.1.el8_6.x86_64  -y /usr/src/kernels/ 

4.18.0-372.32.1.el8_6.x86_64:
  simple-procfs-kmod.ko:
    kmod_name: simple-procfs-kmod.ko
    modinfo:
      author: Liran B.H
      depends: ''
      filename: /home/cprocter/engineering/ksc_reporter/../simple-kmod/simple-procfs-kmod.ko
      license: Dual BSD/GPL
      name: simple_procfs_kmod
      parm:
      - description: int
        name: number
      rhelversion: '8.6'
      srcversion: A2DFD8F444A2384BAF1957A
      vermagic: 4.18.0-372.26.1.el8_6.x86_64 SMP mod_unload modversions
      version: 29092b3
    symbols:
      stable:
        changed: []
        unchanged:
        - __fentry__
        - __stack_chk_fail
        - copy_user_enhanced_fast_string
        - copy_user_generic_string
        - copy_user_generic_unrolled
        - fortify_panic
        - param_ops_int
        - printk
        - sprintf
        - sscanf
        - strnlen
      unknown: []
      unstable:
        changed: []
        unchanged:
        - proc_create
        - proc_remove
    version: 4.18.0-372.26.1.el8_6.x86_64 SMP mod_unload modversions
```

### analyseimage.go

**still under development, use at your own risk!**

analyseimage.go can be used to run ksc_reporter.py against the kmods provided by a driver container. It will pull the image down, search through it for .ko files and make a single run against all of them (so dependancies between the found kmods are resolved). 

It is intended for use with the (Kernel Module Management operator)[https://github.com/kubernetes-sigs/kernel-module-management] but is **still under development, use at your own risk!**

Building (yes its missing makefiles etc again **still under development, use at your own risk!**):

```
go build ./analyseimage.go
```
help:
```
~# ./analyseimage -h
Usage of ./analyseimage:
  -image string
        name of the image to sign
  -insecure
        images can be pulled from an insecure (plain HTTP) registry
  -kernel string
        colon seperated list of kernels to test against
  -long
        produce a long form report
  -quiet
        supress log messages
  -skip-tls-verify
        do not check TLS certs on pull
```
Example:
```
~# ./analyseimage -image quay.io/chrisp262/minimal-driver:kmmo -kernel 4.18.0-425.3.1.el8.x86_64:4.18.0-372.26.1.el8_6.x86_64:4.18.0-372.26.1.el8_6.x86_64 -quiet

4.18.0-372.26.1.el8_6.x86_64:
  simple-kmod.ko:
    stable:
      changed: 0
      unchanged: 2
    unknown: 0
    unstable:
      changed: 0
      unchanged: 0
  simple-procfs-kmod.ko:
    stable:
      changed: 0
      unchanged: 11
    unknown: 0
    unstable:
      changed: 0
      unchanged: 2
4.18.0-425.3.1.el8.x86_64:
  simple-kmod.ko:
    stable:
      changed: 0
      unchanged: 2
    unknown: 0
    unstable:
      changed: 0
      unchanged: 1
  simple-procfs-kmod.ko:
    stable:
      changed: 0
      unchanged: 11
    unknown: 0
    unstable:
      changed: 0
      unchanged: 3
```
