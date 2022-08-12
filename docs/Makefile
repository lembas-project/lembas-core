# Makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
BUILDDIR      = build
SOURCEDIR	  = source

# Internal variables.
ALLSPHINXOPTS   = -d $(BUILDDIR)/doctrees $(SPHINXOPTS) source

.PHONY: help
help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  html       to make standalone HTML files"
	@echo "  live       to make standalone HTML files and serve via sphinx-autobuild"

.PHONY: clean
clean:
	rm -rf $(BUILDDIR)/*

.PHONY: api-docs
api-docs:
	sphinx-apidoc -f -o source/api ../src/lembas -H "API Docs"

.PHONY: html
html: api-docs
	$(SPHINXBUILD) -b html $(ALLSPHINXOPTS) $(BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR)/html."

.PHONY: live
live: api-docs
	sphinx-autobuild "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O) --watch ../src
