PROJECT_NAME ?= backendschool2019
VERSION = $(shell python3 setup.py --version | tr '+' '-')
PROJECT_NAMESPACE ?= alvassin
REGISTRY_IMAGE ?= $(PROJECT_NAMESPACE)/$(PROJECT_NAME)

all:
	@echo "make devenv		- Create & setup development virtual environment"
	@echo "make lint		- Check code with pylama"
	@echo "make postgres	- Start postgres container"
	@echo "make clean		- Remove files created by distutils"
	@echo "make test		- Run tests"
	@echo "make sdist		- Make source distribution"
	@echo "make docker		- Build a docker image"
	@echo "make upload		- Upload docker image to the registry"
	@exit 0

clean:
	rm -fr *.egg-info dist

devenv: clean
	rm -rf env
	# создаем новое окружение
	python3.8 -m venv env
	# обновляем pip
	env/bin/pip install -U pip
	# устанавливаем основные + dev зависимости из extras_require (см. setup.py)
	env/bin/pip install -Ue '.[dev]'

lint:
	env/bin/pylama

postgres:
	docker stop analyzer-postgres || true
	docker run --rm --detach --name=analyzer-postgres \
		--env POSTGRES_USER=user \
		--env POSTGRES_PASSWORD=hackme \
		--env POSTGRES_DB=analyzer \
		--publish 5432:5432 postgres

test: lint postgres
	env/bin/pytest -vv --cov=analyzer --cov-report=term-missing tests

sdist: clean
	# официальный способ дистрибуции python-модулей
	python3 setup.py sdist

docker: sdist
	docker build --target=api -t $(PROJECT_NAME):$(VERSION) .

upload: docker
	docker tag $(PROJECT_NAME):$(VERSION) $(REGISTRY_IMAGE):$(VERSION)
	docker tag $(PROJECT_NAME):$(VERSION) $(REGISTRY_IMAGE):latest
	docker push $(REGISTRY_IMAGE):$(VERSION)
	docker push $(REGISTRY_IMAGE):latest
