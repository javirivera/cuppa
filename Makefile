PREFIX ?= /usr/local
BINDIR  = $(PREFIX)/bin

.PHONY: install uninstall

install:
	install -d "$(BINDIR)"
	install -m 0755 cuppa.py "$(BINDIR)/cuppa"
	@echo "✓ Installed cuppa to $(BINDIR)/cuppa"

uninstall:
	rm -f "$(BINDIR)/cuppa"
	@echo "✓ Removed $(BINDIR)/cuppa"
