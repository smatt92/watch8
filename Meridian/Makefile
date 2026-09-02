# MERIDIAN - Watch Face Format v2 build loop.
#
# Watch Face Format is declarative XML. This project contains no Java/Kotlin
# sources and none are ever to be added; see ../CLAUDE.md.
#
#   make tools      build wff-validator + memory-footprint from google/watchface
#   make assets     (not applicable: MERIDIAN drawables are design exports)
#   make validate   XSD-validate watchface.xml at WFF v2, fail on any SEVERE
#   make assemble   build the APK
#   make memcheck   memory footprint of the built APK, fail if over limit
#   make deploy     assemble, install, set as the active watch face
#   make logs       logcat filtered to the Watch Face Format runtime
#   make check      validate + assemble + memcheck
#
# Device targets (see `make pair-help` for the full wireless debugging flow):
#   make devices    list attached devices
#   make pair       adb pair (PAIR_HOST=..., PAIR_CODE=...)
#   make connect    adb connect (CONNECT_HOST=...)

SHELL := /bin/bash

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WFF_VERSION      ?= 2
APP_ID           ?= com.watch8.meridian
MODULE           ?= watchface
BUILD_TYPE       ?= release

# Memory limits. These mirror the values documented in google/watchface
# play-validations/README.md as reasonable evaluation settings.
AMBIENT_LIMIT_MB ?= 10
ACTIVE_LIMIT_MB  ?= 100

# adb. Set SERIAL=<host:port> when more than one device is attached.
ADB              ?= adb
SERIAL           ?=
ADB_TARGET       := $(ADB) $(if $(SERIAL),-s $(SERIAL),)

WFF_RUNTIME      := com.google.wear.watchface.runtime

WATCHFACE_XML    := $(MODULE)/src/main/res/raw/watchface.xml
ifeq ($(BUILD_TYPE),release)
GRADLE_VARIANT   := Release
else ifeq ($(BUILD_TYPE),debug)
GRADLE_VARIANT   := Debug
else
$(error BUILD_TYPE must be 'debug' or 'release', got '$(BUILD_TYPE)')
endif
GRADLE_TASK      := assemble$(GRADLE_VARIANT)
APK              := $(MODULE)/build/outputs/apk/$(BUILD_TYPE)/$(MODULE)-$(BUILD_TYPE).apk

# Toolchain, built from source out of google/watchface.
TOOLS_DIR        := .tools
WF_REPO          := $(TOOLS_DIR)/watchface
WF_REPO_URL      ?= https://github.com/google/watchface.git
VALIDATOR_JAR    := $(TOOLS_DIR)/wff-validator.jar
MEMORY_JAR       := $(TOOLS_DIR)/memory-footprint.jar
VALIDATE_LOG     := $(TOOLS_DIR)/validate.log

.PHONY: help tools assets validate assemble memcheck deploy install set-watchface \
        logs logs-all check devices pair connect pair-help clean clean-tools

help:
	@sed -n '2,22p' $(MAKEFILE_LIST) | sed 's/^# \{0,1\}//'

# ---------------------------------------------------------------------------
# Toolchain
# ---------------------------------------------------------------------------
tools: $(VALIDATOR_JAR) $(MEMORY_JAR)

$(WF_REPO):
	@mkdir -p $(TOOLS_DIR)
	git clone --depth 1 $(WF_REPO_URL) $(WF_REPO)

# The clone is driven from inside the jar recipes rather than as an order-only
# prerequisite, so an already-built jar never triggers a clone.
# The wff-validator jar is produced by the vendored WFF specification project.
$(VALIDATOR_JAR):
	@$(MAKE) --no-print-directory $(WF_REPO)
	cd $(WF_REPO)/play-validations && ./gradlew :validator:executable-jar
	@mkdir -p $(TOOLS_DIR)
	cp $(WF_REPO)/third_party/wff/specification/validator/build/libs/wff-validator.jar $@

$(MEMORY_JAR):
	@$(MAKE) --no-print-directory $(WF_REPO)
	cd $(WF_REPO)/play-validations && ./gradlew :memory-footprint:executable-jar
	@mkdir -p $(TOOLS_DIR)
	cp $(WF_REPO)/play-validations/memory-footprint/build/libs/memory-footprint.jar $@

# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------
assets:
	@echo "MERIDIAN drawables are design exports, not generated." >&2
	@echo "Re-export from the design, then strip the caBX chunk (see ../CLAUDE.md)." >&2
	@exit 2

# ---------------------------------------------------------------------------
# validate: XSD validation of watchface.xml. Any SEVERE fails the build.
# ---------------------------------------------------------------------------
validate: $(VALIDATOR_JAR)
	@echo "==> wff-validator: $(WATCHFACE_XML) against WFF v$(WFF_VERSION)"
	@java -jar $(VALIDATOR_JAR) $(WFF_VERSION) --stop-on-fail $(WATCHFACE_XML) \
	    > $(VALIDATE_LOG) 2>&1; status=$$?; \
	  cat $(VALIDATE_LOG); \
	  severe=$$(grep -c '^SEVERE:' $(VALIDATE_LOG) || true); \
	  if [ "$$severe" -gt 0 ]; then \
	    echo ""; \
	    echo "FAILED: $$severe SEVERE finding(s) from wff-validator."; \
	    exit 1; \
	  fi; \
	  if [ $$status -ne 0 ]; then \
	    echo ""; \
	    echo "FAILED: wff-validator exited $$status."; \
	    exit $$status; \
	  fi; \
	  echo "OK: no SEVERE findings."

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
assemble:
	./gradlew :$(MODULE):$(GRADLE_TASK)

$(APK): assemble

# ---------------------------------------------------------------------------
# memcheck: asset memory footprint. Non-zero exit if over either limit.
# ---------------------------------------------------------------------------
memcheck: $(MEMORY_JAR) assemble
	@echo "==> memory-footprint: $(APK)"
	@echo "    limits: active $(ACTIVE_LIMIT_MB) MB, ambient $(AMBIENT_LIMIT_MB) MB"
	java -jar $(MEMORY_JAR) \
	  --watch-face $(APK) \
	  --schema-version $(WFF_VERSION) \
	  --ambient-limit-mb $(AMBIENT_LIMIT_MB) \
	  --active-limit-mb $(ACTIVE_LIMIT_MB) \
	  --apply-v1-offload-limitations \
	  --estimate-optimization \
	  --verbose

check: validate assemble memcheck
	@echo "==> validate + assemble + memcheck all passed"

# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------
deploy: validate assemble install set-watchface
	@echo "==> deployed $(APP_ID); check the watch."

install:
	@echo "==> installing $(APK)"
	$(ADB_TARGET) install -r $(APK)

set-watchface:
	@echo "==> setting $(APP_ID) as the active watch face"
	$(ADB_TARGET) shell am broadcast \
	  -a com.google.android.wearable.app.DEBUG_SURFACE \
	  --es operation set-watchface \
	  --es watchFaceId '$(APP_ID)'

# Runtime errors surface in the WFF runtime process, not in our package -- a
# WFF watch face has no process of its own.
logs:
	@pid=$$($(ADB_TARGET) shell pidof -s $(WFF_RUNTIME) | tr -d '\r'); \
	  if [ -z "$$pid" ]; then \
	    echo "$(WFF_RUNTIME) is not running; is a WFF watch face active?" >&2; \
	    exit 1; \
	  fi; \
	  echo "==> logcat pid=$$pid ($(WFF_RUNTIME)), warnings and errors"; \
	  $(ADB_TARGET) logcat --pid=$$pid '*:W'

logs-all:
	@pid=$$($(ADB_TARGET) shell pidof -s $(WFF_RUNTIME) | tr -d '\r'); \
	  $(ADB_TARGET) logcat --pid=$$pid

devices:
	$(ADB) devices -l

pair:
	@if [ -z "$(PAIR_HOST)" ] || [ -z "$(PAIR_CODE)" ]; then \
	  echo "usage: make pair PAIR_HOST=<ip:pairing-port> PAIR_CODE=<6-digit code>" >&2; \
	  exit 2; \
	fi
	$(ADB) pair $(PAIR_HOST) $(PAIR_CODE)

connect:
	@if [ -z "$(CONNECT_HOST)" ]; then \
	  echo "usage: make connect CONNECT_HOST=<ip:port>" >&2; \
	  exit 2; \
	fi
	$(ADB) connect $(CONNECT_HOST)

pair-help:
	@echo "Wireless debugging: Galaxy Watch 8 (Wear OS 6)"
	@echo ""
	@echo "  On the watch, once:"
	@echo "    Settings > About watch > Software info > tap 'Software version' 7x"
	@echo "    Settings > Developer options > ADB debugging          -> On"
	@echo "    Settings > Developer options > Wireless debugging     -> On"
	@echo "    Keep the watch on the same Wi-Fi network as this machine."
	@echo ""
	@echo "  1. Watch: Wireless debugging > Pair new device."
	@echo "     Note the pairing IP:PORT and the 6-digit code."
	@echo "     make pair PAIR_HOST=<ip:pairing-port> PAIR_CODE=<code>"
	@echo ""
	@echo "  2. Watch: Wireless debugging main screen shows IP & Port"
	@echo "     (a DIFFERENT port from the pairing one)."
	@echo "     make connect CONNECT_HOST=<ip:port>"
	@echo ""
	@echo "  3. make devices    # expect '<ip:port>  device'"
	@echo "  4. make deploy SERIAL=<ip:port>"
	@echo ""
	@echo "  Pairing is once per machine; connect again after a watch reboot."

# ---------------------------------------------------------------------------
clean:
	./gradlew clean

clean-tools:
	rm -rf $(TOOLS_DIR)
