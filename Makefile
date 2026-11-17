# directories
WORKING_DIRECTORY := $(dir $(lastword $(MAKEFILE_LIST)))
BUILD_DIRECTORY ?= $(WORKING_DIRECTORY)build
DEBIAN_BUILD_DIRECTORY = $(BUILD_DIRECTORY)/Debian

# version
VERSION_MAJOR := $(shell cat $(WORKING_DIRECTORY)/interface/main_window.py | grep \'major\': | cut -f 2 -d : | tr -d [:space:][,])
VERSION_MINOR := $(shell cat $(WORKING_DIRECTORY)/interface/main_window.py | grep \'minor\': | cut -f 2 -d : | tr -d [:space:][,])
VERSION_BUILD := $(shell cat $(WORKING_DIRECTORY)/interface/main_window.py | grep \'build\': | cut -f 2 -d : | tr -d [:space:][,])
VERSION_STAGE := $(shell cat $(WORKING_DIRECTORY)/interface/main_window.py | grep \'stage\': | cut -f 2 -d : | tr -d [:space:][\'][,])

# generate file name based on version
ifeq ($(VERSION_STAGE),f)
VERSION = $(VERSION_MAJOR).$(VERSION_MINOR).$(VERSION_BUILD)
FILE_NAME = freesteel-$(VERSION_MAJOR).$(VERSION_MINOR)-$(VERSION_BUILD)
else
VERSION = $(VERSION_MAJOR).$(VERSION_MINOR)$(VERSION_STAGE).$(VERSION_BUILD)
FILE_NAME = freesteel-$(VERSION_MAJOR).$(VERSION_MINOR)$(VERSION_STAGE)-$(VERSION_BUILD)
endif

# variables used in packages
RELEASE ?= 1
PACKAGER ?= ""

# name under which desktop finds the program, same as Application.ID
APPLICATION_ID = org.freesteel.FreeSteel

# additional directories
FILE_PATH = $(BUILD_DIRECTORY)/$(FILE_NAME)
DEB_FILE_PATH = $(BUILD_DIRECTORY)/freesteel-$(VERSION)-$(RELEASE).all.deb
APP_FILE_PATH = $(FILE_PATH).app

# prepare help
define HELP
Usage:
	dist       - create a distribution tgz file
	dist-deb   - create a .deb package for Debian, Mint, Ubuntu
	dist-all   - create all packages
	standalone - create a single-file executable (zip archive with a shebang)
	clean      - remove all build files
	version    - print FreeSteel version
	help       - print this help

Options for dist-* passed through environment variables:
	RELEASE=1   - release number
	PACKAGER="" - packagers name (e.i. "John Smith <mail@example.com>")
endef
export HELP

# install program to fake root. library goes among other Python packages,
# interface is kept in program's own directory since its name is too common
define DEBIAN_INSTALL
	rm -rf "$(DEBIAN_BUILD_DIRECTORY)"
	mkdir -p "$(DEBIAN_BUILD_DIRECTORY)"
	mkdir -p "$(DEBIAN_BUILD_DIRECTORY)/usr/share/freesteel"
	install -d "$(DEBIAN_BUILD_DIRECTORY)/usr/lib/python3/dist-packages/freesteel"

	tar -xf $(FILE_PATH).tar -C $(BUILD_DIRECTORY)
	install -Dm755 $(WORKING_DIRECTORY)/dist/freesteel "$(DEBIAN_BUILD_DIRECTORY)/usr/bin/freesteel"
	cp -r $(BUILD_DIRECTORY)/FreeSteel/freesteel/* "$(DEBIAN_BUILD_DIRECTORY)/usr/lib/python3/dist-packages/freesteel"
	cp -r $(BUILD_DIRECTORY)/FreeSteel/interface "$(DEBIAN_BUILD_DIRECTORY)/usr/share/freesteel"
	install -Dm644 "$(BUILD_DIRECTORY)/FreeSteel/images/freesteel.svg" "$(DEBIAN_BUILD_DIRECTORY)/usr/share/icons/hicolor/scalable/apps/$(APPLICATION_ID).svg"
	install -Dm644 "$(BUILD_DIRECTORY)/FreeSteel/FreeSteel.desktop" "$(DEBIAN_BUILD_DIRECTORY)/usr/share/applications/$(APPLICATION_ID).desktop"
endef

# configuration options
all: version help

# files are taken from working directory, so changes which are not
# committed yet are packaged as well. files ignored by git are left out
archive:
	$(info Creating release archive...)
	mkdir -p $(BUILD_DIRECTORY)
	cd $(WORKING_DIRECTORY) && git ls-files --cached --others --exclude-standard --deduplicate | tar --create --file=$(abspath $(FILE_PATH)).tar --transform='s,^,FreeSteel/,' --ignore-failed-read --files-from=-

dist: archive
	$(info Compressing release archive...)
	gzip -9 $(FILE_PATH).tar
	mv $(FILE_PATH).tar.gz $(FILE_PATH).tgz
	sha256sum $(FILE_PATH).tgz > $(FILE_PATH).tgz.sha256

dist-deb: archive
	$(info Building package for Debian, Mint, Ubuntu...)
	$(DEBIAN_INSTALL)
	mkdir -p $(DEBIAN_BUILD_DIRECTORY)/DEBIAN
	cp $(WORKING_DIRECTORY)/dist/control $(DEBIAN_BUILD_DIRECTORY)/DEBIAN
	sed -i "s/@version@/$(VERSION)/" $(DEBIAN_BUILD_DIRECTORY)/DEBIAN/control
	sed -i "s/@packager@/$(PACKAGER)/" $(DEBIAN_BUILD_DIRECTORY)/DEBIAN/control
	sed -i "s/@size@/`du --summarize $(DEBIAN_BUILD_DIRECTORY) | cut -f 1`/" $(DEBIAN_BUILD_DIRECTORY)/DEBIAN/control
	fakeroot dpkg-deb --build $(DEBIAN_BUILD_DIRECTORY)
	mv $(DEBIAN_BUILD_DIRECTORY).deb $(DEB_FILE_PATH)
	sha256sum $(DEB_FILE_PATH) > $(DEB_FILE_PATH).sha256

dist-all: dist-deb standalone

clean:
	$(RM) -rf $(BUILD_DIRECTORY)

version:
	$(info FreeSteel $(VERSION))

standalone:
	$(info Building standalone executable...)
	mkdir -p $(BUILD_DIRECTORY)
	$(RM) -f $(FILE_PATH).zip
	cd $(WORKING_DIRECTORY) && zip --quiet $(abspath $(FILE_PATH)).zip -r freesteel interface images -x '*.pyc' -x '*/__pycache__/*'
	cd $(WORKING_DIRECTORY) && zip --quiet --junk-paths $(abspath $(FILE_PATH)).zip interface/__main__.py
	echo '#!/usr/bin/env python3' > $(APP_FILE_PATH)
	cat $(FILE_PATH).zip >> $(APP_FILE_PATH)
	$(RM) -f $(FILE_PATH).zip
	chmod a+x $(APP_FILE_PATH)
	sha256sum $(APP_FILE_PATH) > $(APP_FILE_PATH).sha256

help:
	@echo "$$HELP"

.PHONY: default archive dist dist-deb dist-all standalone clean version help
