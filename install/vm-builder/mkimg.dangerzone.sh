profile_dangerzone() {
	profile_standard
	profile_abbrev="dangerzone"
	title="Dangerzone"
	desc="Copied from virt but with extra apks and an apkovl"
	arch="aarch64 armv7 x86 x86_64"
	kernel_addons=
	kernel_flavors="virt"
	kernel_cmdline="console=tty0 console=ttyS0,115200"
	syslinux_serial="0 115200"
	apkovl="genapkovl-dangerzone.sh"
    apks="$apks podman dropbear autossh python3 sudo"
}