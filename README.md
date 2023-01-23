## This script returns yaml formatted reports on the symbols used by a kernel module and whether they conform to the RHEL list of stable symbols (i.e. those whos usage remains the same across all minor versions of a RHEL release) and which are not available in a given kernel version. It acts as a wrapper around the ksc tool.

### Example usage
```
~# ./analyse_kmod.py  -k ./cfg80211_rhel8_7.ko -f ./ksc-report.txt -o  -y /usr/src/kernels/4.18.0-372.26.1.el8_6.x86_64/Module.symvers -y /usr/src/kernels/4.18.0-372.26.1.el8_6.x86_64/Module.symvers -y /usr/src/kernels/4.18.0-372.32.1.el8_6.x86_64/Module.symvers  -y /usr/src/kernels/4.18.0-425.3.1.el8.x86_64/Module.symvers

4.18.0-372.26.1.el8_6.x86_64:
  cfg80211_rhel8_7.ko:
    stable: 104
    unknown: 2
    unstable: 93
4.18.0-372.32.1.el8_6.x86_64:
  cfg80211_rhel8_7.ko:
    stable: 104
    unknown: 1
    unstable: 94
4.18.0-425.3.1.el8.x86_64:
  cfg80211_rhel8_7.ko:
    stable: 104
    unknown: 0
    unstable: 95
```
