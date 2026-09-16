SC_ADAT_JACK_PROBE_VERSION = 1
SC_ADAT_JACK_PROBE_SITE = $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/package/sc-adat-jack-probe
SC_ADAT_JACK_PROBE_SITE_METHOD = local
SC_ADAT_JACK_PROBE_DEPENDENCIES = jack2
define SC_ADAT_JACK_PROBE_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) $(@D)/sc-adat-jack-probe.c -ljack $(TARGET_LDFLAGS) -o $(@D)/sc-adat-jack-probe
endef
define SC_ADAT_JACK_PROBE_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/sc-adat-jack-probe $(TARGET_DIR)/usr/bin/sc-adat-jack-probe
endef
$(eval $(generic-package))
