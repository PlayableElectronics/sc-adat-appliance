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
inittab mounts for proc/sys/devpts/tmpfs/run, tty1 and ttyS0 gettys, and
explicit progress writes to `/dev/tty0` and `/dev/ttyS0`. tty1 is a physically
accessible development recovery shell on tty1 only; the root password hash is
locked and the shell has no password prompt. SSH does not accept passwords
(`Dropbear -s`) and uses only the supplied root `authorized_keys`. No fixed or
blank legacy password is restored.

S35network selects the first physical, non-loopback Ethernet interface exposed
through `/sys/class/net/*/device`, so it accepts eno1 or eth0 without assuming
either name. It starts exactly one background dhcpcd and bounds address polling
to 12 seconds. Failure continues to local diagnostics and audio startup.
S40jack, S50scsynth, and S60self-test have bounded waits and readiness markers;
the self-test does not run the audio checks until scsynth has published a JACK
port.

## Hardware gate procedure

This work intentionally stops before deployment. The exact first candidate
failure was recovered by selecting Debian through the GRUB one-shot recovery
path; `saved_entry` remained Debian and `next_entry` was cleared. For the next
candidate boot, record tty0 and ttyS0 output, observe the complete progress
sequence, verify `eno1`/the selected interface and the RME card, then return to
Debian if any required milestone is absent. If the machine is unresponsive,
power-cycle only after waiting the bounded startup window; use the existing
GRUB recovery selection, verify `next_entry` is empty and `saved_entry` still
identifies Debian, then inspect the captured serial output. No second-boot
hardware observation has been made in this postmortem because candidate-1 has
not been staged or booted.
