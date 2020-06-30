#!/usr/bin/make -f

ifneq ($(wildcard /usr/share/sourcemgr/make/py),)
include /usr/share/sourcemgr/make/py
else
%:
		@echo "Please use 'python setup.py'."
		@exit 1
endif
