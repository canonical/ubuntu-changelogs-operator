NAME:=ubuntu-changelogs
CHARM:=$(NAME)_amd64.charm
TEST_VM:=juju-sandbox-$(NAME)

.PHONY: init
init:
	uv lock

.PHONY: quality
quality:
	tox run -e format
	tox run -e lint

.PHONY: pack
pack: quality unit-tests
	charmcraft pack

.PHONY: unit-tests
unit-tests:
	tox -e unit

.PHONY: setup-integration-tests
setup-integration-tests:
	multipass launch --cpus 4 --memory 8G --disk 60G --name $(TEST_VM) 26.04
	multipass exec $(TEST_VM) -- sudo snap install --classic concierge
	multipass exec $(TEST_VM) -- sudo concierge prepare -p machine --extra-snaps astral-uv
	multipass exec $(TEST_VM) -- uv tool install tox --with tox-uv
	multipass exec $(TEST_VM) -- uv tool update-shell
	multipass stop $(TEST_VM)
	multipass snapshot $(TEST_VM)
	multipass mount --type native . $(TEST_VM):$(NAME)

.PHONY: teardown-integration-tests
teardown-integration-tests:
	multipass delete --purge $(TEST_VM)

.PHONY: integration-tests
integration-tests: pack
	multipass exec $(TEST_VM) -- bash -lc 'tox run -e integration'

.PHONY: deploy
deploy:
	juju deploy ./$(CHARM)

.PHONY: refresh
refresh:
	juju refresh $(NAME) --path ./$(CHARM)

.PHONY: remove
remove:
	juju remove-application $(NAME)

.PHONY: logs
logs:
	juju debug-log --include $(NAME)

.PHONY: smoke
smoke:
	./tests/smoke.sh $(NAME)
