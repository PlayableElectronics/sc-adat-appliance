SC_ADAT_TONE_TEST_VERSION = 2
SC_ADAT_TONE_TEST_SITE = $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/package/sc-adat-tone-test
SC_ADAT_TONE_TEST_SITE_METHOD = local
SC_ADAT_TONE_TEST_DEPENDENCIES = jack2 supercollider-headless
define SC_ADAT_TONE_TEST_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) $(@D)/sc-adat-tone-osc.c $(TARGET_LDFLAGS) -o $(@D)/sc-adat-tone-osc
endef
define SC_ADAT_TONE_TEST_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/sc-adat-tone-osc $(TARGET_DIR)/usr/bin/sc-adat-tone-osc
	$(INSTALL) -D -m 0755 $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/board/dell-optiplex-7010/rootfs-overlay/usr/bin/sc-adat-tone-test $(TARGET_DIR)/usr/bin/sc-adat-tone-test
	$(INSTALL) -D -m 0755 $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/board/dell-optiplex-7010/rootfs-overlay/usr/bin/sc-adat-report $(TARGET_DIR)/usr/bin/sc-adat-report
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/supercollider/synthdefs/sc-adat-tone.scd $(TARGET_DIR)/usr/share/sc-adat/sc-adat-tone.scd
	$(INSTALL) -D -m 0755 $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/payload/runtime/payload-consumer $(TARGET_DIR)/usr/bin/sc-adat-payload-consumer
endef
$(eval $(generic-package))
