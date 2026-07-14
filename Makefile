NAME:=ubuntu-changelogs-operator
CHARM:=$(NAME)_amd64.charm

.PHONY: init
init:
	uv lock

.PHONY: quality
quality:
	tox run -e format
	tox run -e lint

.PHONY: pack
pack: quality
	charmcraft pack

.PHONY: unit
unit:
	tox -e unit

.PHONY: integration
integration:
	tox run -e integration

.PHONY: deploy
deploy:
	juju deploy ./$(CHARM)

.PHONY: refresh
refresh:
	juju refresh $(NAME) --path ./$(CHARM)

.PHONY: remove
remove:
	juju remove-application --force --no-wait $(NAME)

.PHONY: logs
logs:
	juju debug-log --include $(NAME)

.PHONY: smoke
smoke:
	./tests/smoke.sh $(NAME)
