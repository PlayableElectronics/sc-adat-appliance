# Candidate-1 postmortem and deployment gate

The exact first deployed files in `/boot/sc-adat/candidate-1/` matched the
previous repository artifact byte-for-byte. Its kernel was 6.12.107 and
`PREEMPT_RT=y`, but `CONFIG_DRM` was unset. `CONFIG_VT` and `CONFIG_VGA_CONSOLE`
were present, while there was no DRM/framebuffer display driver. The rootfs
also used Buildroot's serial getty, hard-coded `eth0`, generated DHCP startup,
and startup scripts that did not make all readiness waits or progress visible
on both consoles. These facts explain the black/unobservable failure more
strongly than the stale DHCP entries, which are not proof of a live appliance.

Linux 6.12 rejects i915 with PREEMPT_RT (`drivers/gpu/drm/i915/Kconfig` has
`depends on !PREEMPT_RT`). The new target therefore enables DRM, nouveau for
the currently detected GT 730, and VESA/EFI/simple framebuffer fallbacks,
alongside VT/VGA/framebuffer console. The host-only evidence is the current
PCI inventory; display-driver success and RME operation remain hardware-only
checks.

The GRUB command line remains `console=tty0 console=ttyS0,115200n8`. The
kernel sends printk output to both consoles; because ttyS0 is listed last it
may be the preferred `/dev/console`, so startup code does not rely on that
device and writes progress explicitly to both tty0 and ttyS0.

The initramfs now has an explicit `/sbin/init`, BusyBox/musl userspace,
inittab mounts for proc/sys/devpts/tmpfs/run, tty1 and ttyS0 gettys, explicit
progress writes to `/dev/tty0` and `/dev/ttyS0`, and one final automatic boot
report at `/var/log/sc-adat-boot-report.log`. tty1 is the physically
accessible recovery console. Dropbear root/password login uses the temporary
`scadat` password as a clearly labeled development-only policy; no
`authorized_keys` file is required.

S35network selects the first physical, non-loopback Ethernet interface exposed
through `/sys/class/net/*/device`, so it accepts eno1 or eth0 without assuming
either name. It starts exactly one background dhcpcd and bounds address polling
to 12 seconds. Failure continues to local diagnostics and audio startup.
S40jack and S50scsynth have bounded waits, stale-marker removal, live-process
checks, explicit JACK parser/runtime validation, and readiness markers. The
final report runs after all services have either started or failed.

## Hardware gate procedure

The reviewed deployment helper now stages candidate-1, verifies byte-for-byte
checksums, regenerates and checks GRUB, preserves Debian as `saved_entry`, and
sets `next_entry=sc-adat-candidate-1` without rebooting. QEMU covers all
software-testable paths; physical Digi9652/ALSA/JACK/scsynth readiness remains
the hardware gate and is automatically reported on both consoles.
