################################################################################
#
# supercollider-headless
#
################################################################################

SUPERCOLLIDER_HEADLESS_VERSION = 3.13.0
SUPERCOLLIDER_HEADLESS_SITE = https://github.com/supercollider/supercollider/archive/refs/tags
SUPERCOLLIDER_HEADLESS_SOURCE = Version-3.13.0.tar.gz
SUPERCOLLIDER_HEADLESS_HASH = 143c0d6c2f0a2a52ee1b6819f176f9e20974187090093cdd64338a61fcdcd399
SUPERCOLLIDER_HEADLESS_INSTALL_STAGING = NO
SUPERCOLLIDER_HEADLESS_INSTALL_TARGET = YES
SUPERCOLLIDER_HEADLESS_DEPENDENCIES = alsa-lib jack2 libsndfile libsamplerate
SUPERCOLLIDER_HEADLESS_CONF_OPTS = \
    -DAUDIOAPI=jack \
    -DSC_QT=OFF \
    -DSC_IDE=OFF \
    -DSC_ED=OFF \
    -DSC_EL=OFF \
    -DSC_VIM=OFF \
    -DSC_HIDAPI=OFF \
    -DSC_ABLETON_LINK=OFF \
    -DNO_X11=ON \
    -DUSE_CCACHE=OFF \
    -DFFT_GREEN=ON \
    -DINSTALL_HELP=OFF \
    -DSC_DOC_RENDER=OFF \
    -DENABLE_TESTSUITE=OFF

# GitHub source archives preserve submodule directories but not their contents.
# Fetch the exact gitlinks recorded by Version-3.13.0 before CMake configures.
define SUPERCOLLIDER_HEADLESS_FETCH_SUBMODULES
	set -eu; \
	for spec in \
		"external_libraries/nova-simd https://github.com/timblechmann/nova-simd.git 2bdc68bc5704a42578300a4c18411df2405cb307" \
		"external_libraries/nova-tt https://github.com/timblechmann/nova-tt.git 55da93741e76632579b63004d3378139e32d634f" \
		"external_libraries/yaml-cpp https://github.com/supercollider/yaml-cpp.git 728e26e42645d4d70ca65522990f915f47b47a50" \
		"external_libraries/portaudio/portaudio_submodule https://github.com/PortAudio/portaudio.git 147dd722548358763a8b649b3e4b41dfffbcfbb6"; do \
		set -- $$spec; dir="$(@D)/$$1"; mkdir -p "$$dir"; \
		git -C "$$dir" init -q; git -C "$$dir" fetch -q --depth 1 "$$2" "$$3"; git -C "$$dir" checkout -q --detach FETCH_HEAD; \
	done
endef
SUPERCOLLIDER_HEADLESS_POST_EXTRACT_HOOKS += SUPERCOLLIDER_HEADLESS_FETCH_SUBMODULES

$(eval $(cmake-package))
