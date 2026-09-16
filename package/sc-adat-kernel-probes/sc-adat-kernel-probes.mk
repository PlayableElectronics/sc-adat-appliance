################################################################################
#
# sc-adat-kernel-probes
#
################################################################################

SC_ADAT_KERNEL_PROBES_VERSION = 1
SC_ADAT_KERNEL_PROBES_SITE = $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/package/sc-adat-kernel-probes
SC_ADAT_KERNEL_PROBES_SITE_METHOD = local
SC_ADAT_KERNEL_PROBES_INSTALL_TARGET = YES

define SC_ADAT_KERNEL_PROBES_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_LDFLAGS) -o $(@D)/sc-adat-kernel-probes $(@D)/sc-adat-kernel-probes.c
endef

define SC_ADAT_KERNEL_PROBES_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/sc-adat-kernel-probes $(TARGET_DIR)/usr/bin/sc-adat-kernel-probes
endef

$(eval $(generic-package))
