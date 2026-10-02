SC_ADAT_RECORDER_VERSION = 1
SC_ADAT_RECORDER_SITE = $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/package/sc-adat-recorder
SC_ADAT_RECORDER_SITE_METHOD = local
SC_ADAT_RECORDER_DEPENDENCIES = jack2 libsndfile python3 alsa-utils util-linux
define SC_ADAT_RECORDER_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) -std=c11 -Wall -Wextra $(@D)/sc-adat-recorder.c -ljack -lsndfile -pthread $(TARGET_LDFLAGS) -o $(@D)/sc-adat-recorder
endef
define SC_ADAT_RECORDER_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/sc-adat-recorder $(TARGET_DIR)/usr/bin/sc-adat-recorder
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/mixer/mixerctl.py $(TARGET_DIR)/usr/lib/sc-adat/mixer/mixerctl.py
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/mixer/recorder_manager.py $(TARGET_DIR)/usr/lib/sc-adat/mixer/recorder_manager.py
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/mixer/recorder_policy.py $(TARGET_DIR)/usr/lib/sc-adat/mixer/recorder_policy.py
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/mixer/contract.py $(TARGET_DIR)/usr/lib/sc-adat/mixer/contract.py
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/mixer/source_map.py $(TARGET_DIR)/usr/lib/sc-adat/mixer/source_map.py
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/control/mixer-control-contract.json $(TARGET_DIR)/usr/lib/sc-adat/control/mixer-control-contract.json
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_SC_ADAT_APPLIANCE_PATH)/payload/config/recording.conf $(TARGET_DIR)/etc/sc-adat/recording.conf
	$(INSTALL) -D -m 0755 $(@D)/sc-adat-mixerctl $(TARGET_DIR)/usr/bin/sc-adat-mixerctl
endef
$(eval $(generic-package))
