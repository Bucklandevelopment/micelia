# =============================================================================
# Micelia — Orquestador del ecosistema UTOP.IA
# =============================================================================
# Makefile orquestador para el flujo completo de desarrollo.
# Ejecuta `make help` para ver todos los targets disponibles.
#
# Usa `uv` (https://astral.sh/uv) si está instalado (10-100× más rápido que pip
# y crea el venv en un solo paso). Si no, cae a `python -m venv` + `pip`.
# Para instalar uv: `make install-uv` o `brew install uv` en macOS.
# =============================================================================

# Configuración del entorno
PYTHON        := python3.13
VENV          := .venv
BIN           := $(VENV)/bin
FRONTEND_DIR  := frontend

# Detección automática de uv. Si no está, usa pip+venv tradicional.
UV := $(shell command -v uv 2>/dev/null)

ifdef UV
  PKG_MGR_NAME := uv
  PIP_INSTALL  := uv pip install --python $(VENV)
  VENV_CREATE  := uv venv --python $(PYTHON) $(VENV)
else
  PKG_MGR_NAME := pip
  PIP_INSTALL  := $(BIN)/pip install
  VENV_CREATE  := $(PYTHON) -m venv $(VENV) && $(BIN)/pip install --upgrade pip setuptools wheel
endif

# Binarios — SIEMPRE invocados directamente desde $(BIN)/<cmd>. NO usamos `uv run`
# porque `uv run` re-sincroniza el venv contra pyproject.toml en cada invocación
# y descarta los extras instalados manualmente (.[dev], respx, pytest-httpx).
# uv sigue dando ventaja en `uv venv` y `uv pip install` (instalación 10-100×).
PYTEST  := $(BIN)/pytest
RUFF    := $(BIN)/ruff
BLACK   := $(BIN)/black
MYPY    := $(BIN)/mypy
MICELIA := $(BIN)/micelia
IDM     := $(BIN)/idm

# Colores ANSI
CYAN   := \033[36m
GREEN  := \033[32m
YELLOW := \033[33m
RED    := \033[31m
BOLD   := \033[1m
RESET  := \033[0m

.DEFAULT_GOAL := help
.PHONY: help setup install-uv venv env-create install install-prod env setup-auth \
        _check-venv _check-port-8888 _check-infra test test-unit test-e2e test-sdk test-fast cov verify \
        lint format typecheck rebrand-verify \
        dev dev-verbose dev-idm _dev-banner frontend-install frontend-dev frontend-build frontend-lint \
        docker-infra docker-up docker-full docker-monitoring docker-health docker-down docker-logs docker-ps \
        clean clean-all version

# Modo verbosidad de `make dev`. Override con `VERBOSE=1 make dev` o `make dev-verbose`.
# DEV_LOG_LEVEL gobierna TANTO uvicorn (--log-level) COMO loguru (env LOG_LEVEL),
# de modo que `make dev` queda realmente silencioso (warnings y errores).
VERBOSE ?= 0
ifeq ($(VERBOSE),1)
  DEV_LOG_LEVEL := debug
  DEV_LOG_FLAGS := --log-level debug --access-log
else
  DEV_LOG_LEVEL := warning
  DEV_LOG_FLAGS := --log-level warning --no-access-log
endif

# =============================================================================
# HELP
# =============================================================================

help: ## Lista todos los targets disponibles
	@printf "\n$(BOLD)$(CYAN)Micelia — Makefile orquestador$(RESET)\n"
	@printf "Gestor detectado: $(BOLD)$(PKG_MGR_NAME)$(RESET)"
	@if [ -z "$(UV)" ]; then printf " $(YELLOW)(instala uv con $(BOLD)make install-uv$(RESET)$(YELLOW) para 10-100× más velocidad)$(RESET)"; fi
	@printf "\n\n"
	@printf "  $(BOLD)Uso:$(RESET) make $(YELLOW)<target>$(RESET)\n\n"
	@printf "$(BOLD)$(GREEN)Setup$(RESET)\n"
	@awk 'BEGIN {FS = ":.*?## "} /^(setup|install-uv|venv|env-create|install|install-prod|env):.*?## / {printf "  $(YELLOW)%-22s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n$(BOLD)$(GREEN)Tests y cobertura$(RESET)\n"
	@awk 'BEGIN {FS = ":.*?## "} /^(test|test-unit|test-e2e|test-sdk|test-fast|cov|verify):.*?## / {printf "  $(YELLOW)%-22s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n$(BOLD)$(GREEN)Calidad de código$(RESET)\n"
	@awk 'BEGIN {FS = ":.*?## "} /^(lint|format|typecheck|rebrand-verify):.*?## / {printf "  $(YELLOW)%-22s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n$(BOLD)$(GREEN)Ejecución local$(RESET)\n"
	@awk 'BEGIN {FS = ":.*?## "} /^(dev|dev-verbose|dev-idm|frontend-install|frontend-dev|frontend-build|frontend-lint):.*?## / {printf "  $(YELLOW)%-22s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n$(BOLD)$(GREEN)Docker / infraestructura$(RESET)\n"
	@awk 'BEGIN {FS = ":.*?## "} /^(docker-infra|docker-up|docker-full|docker-monitoring|docker-health|docker-down|docker-logs|docker-ps):.*?## / {printf "  $(YELLOW)%-22s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n$(BOLD)$(GREEN)Mantenimiento$(RESET)\n"
	@awk 'BEGIN {FS = ":.*?## "} /^(clean|clean-all|version):.*?## / {printf "  $(YELLOW)%-22s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n$(BOLD)$(GREEN)Flujos típicos$(RESET)\n"
	@printf "  $(YELLOW)Setup desde cero:$(RESET)  make setup        # install-uv + install + env + docker-infra\n"
	@printf "  $(YELLOW)Desarrollo:$(RESET)        make dev          # en otra terminal: make frontend-dev\n"
	@printf "  $(YELLOW)Pre-commit:$(RESET)        make verify       # lint + typecheck + test + cov\n"
	@printf "  $(YELLOW)Suite E2E:$(RESET)         make test-e2e\n"
	@printf "  $(YELLOW)Reset completo:$(RESET)    make clean-all install\n\n"

# =============================================================================
# SETUP
# =============================================================================

setup: install-uv install env docker-infra ## Setup completo desde cero: uv + venv + deps + .env + infra docker
	@printf "\n$(GREEN)$(BOLD)✓ Setup completo. Arranca con:$(RESET) make dev\n"

install-uv: ## Instala uv (Astral) si no está presente — gestor moderno 10-100× más rápido
	@if command -v uv >/dev/null 2>&1; then \
		printf "$(GREEN)✓ uv ya instalado:$(RESET) "; uv --version; \
	else \
		printf "$(CYAN)→ Instalando uv desde https://astral.sh/uv/install.sh...$(RESET)\n"; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
		printf "$(YELLOW)⚠ Reabre la terminal o ejecuta:$(RESET) source ~/.local/bin/env\n"; \
		printf "$(YELLOW)  Luego repite $(BOLD)make setup$(RESET)\n"; \
	fi

$(VENV)/bin/python:
	@printf "$(CYAN)→ Creando virtualenv con $(PKG_MGR_NAME) ($(PYTHON))...$(RESET)\n"
	$(VENV_CREATE)

venv: $(VENV)/bin/python ## Crea el virtualenv con Python 3.13 si no existe (uv venv o python -m venv)

env-create: venv ## Alias de `venv` — crea el virtualenv

install: venv ## Instala Micelia + SDK Python + deps de dev + respx/pytest-httpx
	@printf "$(CYAN)→ Instalando Micelia + dependencias de desarrollo con $(PKG_MGR_NAME)...$(RESET)\n"
	$(PIP_INSTALL) -e ".[dev]"
	$(PIP_INSTALL) -e ./sdk/python
	$(PIP_INSTALL) respx pytest-httpx
	@printf "$(GREEN)✓ Instalación completada. CLI: $(BOLD)micelia$(RESET) | SDK: $(BOLD)idm_sdk$(RESET) (importable como MiceliaClient)\n"

install-prod: venv ## Instala solo dependencias de producción (sin pytest, ruff, etc.)
	@printf "$(CYAN)→ Instalando Micelia + SDK (producción) con $(PKG_MGR_NAME)...$(RESET)\n"
	$(PIP_INSTALL) -e "."
	$(PIP_INSTALL) -e ./sdk/python
	@printf "$(GREEN)✓ Producción instalada$(RESET)\n"

env: ## Copia .env.example a .env si no existe
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		printf "$(GREEN)✓ .env creado desde .env.example$(RESET)\n"; \
		printf "$(YELLOW)⚠ Edita .env con tus credenciales antes de arrancar$(RESET)\n"; \
		printf "$(YELLOW)⚠ Genera el hash de password con: $(BOLD)make setup-auth$(RESET)\n"; \
	else \
		printf "$(YELLOW).env ya existe, no se sobrescribe$(RESET)\n"; \
	fi

setup-auth: ## Genera AUTH_PASSWORD_HASH (bcrypt) y lo escribe al .env (default user/pass: admin/admin)
	@if [ ! -f .env ]; then \
		printf "$(RED)✗ .env no existe. Ejecuta primero: $(BOLD)make env$(RESET)\n"; \
		exit 1; \
	fi
	@if grep -q "^AUTH_PASSWORD_HASH=" .env; then \
		printf "$(YELLOW)⚠ .env ya tiene AUTH_PASSWORD_HASH. Para regenerar borra esa línea primero.$(RESET)\n"; \
		exit 0; \
	fi
	@printf "$(CYAN)→ Generando bcrypt hash para password 'admin' (cámbialo después en .env)$(RESET)\n"
	@hash=$$($(BIN)/python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt'], deprecated='auto').hash('admin'))"); \
	if [ -z "$$hash" ]; then \
		printf "$(RED)✗ No se pudo generar el hash. ¿Está passlib instalado? Prueba: $(BOLD)make install$(RESET)\n"; \
		exit 1; \
	fi; \
	printf "\n# Auth (generado por make setup-auth)\n" >> .env; \
	printf "AUTH_USERNAME=admin\n" >> .env; \
	printf "AUTH_PASSWORD_HASH='%s'\n" "$$hash" >> .env; \
	printf "$(GREEN)✓ AUTH_USERNAME=admin + AUTH_PASSWORD_HASH añadidos a .env$(RESET)\n"; \
	printf "$(YELLOW)⚠ Login default:$(RESET) usuario $(BOLD)admin$(RESET) / password $(BOLD)admin$(RESET)\n"; \
	printf "$(YELLOW)⚠ Para cambiar password: borra la línea AUTH_PASSWORD_HASH del .env y vuelve a ejecutar $(BOLD)make setup-auth ADMIN_PASS=<nueva>$(RESET)\n"

# =============================================================================
# TESTS Y COBERTURA
# =============================================================================

_check-venv: ## (interno) detecta venv corrupto por rename de directorio
	@if [ -f "$(VENV)/bin/pytest" ]; then \
		venv_shebang=$$(head -1 $(VENV)/bin/pytest | sed 's|^#!||'); \
		if [ ! -x "$$venv_shebang" ]; then \
			printf "$(RED)✗ venv corrupto detectado$(RESET)\n"; \
			printf "  El intérprete del shebang ya no existe:\n"; \
			printf "    $$venv_shebang\n"; \
			printf "  Esto suele pasar tras renombrar el directorio del repo.\n"; \
			printf "  $(BOLD)Fix:$(RESET) $(BOLD)make clean-all && make install$(RESET)\n"; \
			exit 1; \
		fi \
	fi

_check-port-8888: ## (interno) detecta puerto 8888 ocupado antes de arrancar uvicorn
	@if lsof -nP -iTCP:8888 -sTCP:LISTEN >/dev/null 2>&1; then \
		printf "$(RED)✗ Puerto 8888 ya está ocupado$(RESET)\n"; \
		printf "  Probablemente hay otra instancia de Micelia corriendo:\n\n"; \
		lsof -nP -iTCP:8888 -sTCP:LISTEN 2>/dev/null | head -5; \
		printf "\n  $(BOLD)Si es el container docker idm-core:$(RESET)\n"; \
		printf "      docker stop idm-core\n"; \
		printf "  $(BOLD)Si es un proceso zombie de uvicorn:$(RESET)\n"; \
		printf "      kill -9 \$$(lsof -t -i:8888)\n"; \
		exit 1; \
	fi

_check-infra: ## (interno) detecta si postgres y redis están escuchando antes de arrancar Micelia
	@missing=""; \
	if ! nc -z localhost 5432 2>/dev/null; then missing="$$missing postgres(5432)"; fi; \
	if ! nc -z localhost 6379 2>/dev/null; then missing="$$missing redis(6379)"; fi; \
	if [ -n "$$missing" ]; then \
		printf "$(RED)✗ Infra requerida no responde:$(RESET)%s\n" "$$missing"; \
		printf "  Micelia necesita postgres y redis arriba para inicializar el event store.\n"; \
		printf "  $(BOLD)Fix:$(RESET) levanta la infra y reintenta:\n"; \
		printf "      $(BOLD)make docker-infra$(RESET)   # postgres + redis + ollama\n"; \
		printf "      $(BOLD)make dev$(RESET)\n"; \
		exit 1; \
	fi

test: _check-venv ## Ejecuta TODA la suite (unit + e2e + sdk) en dos pasadas para evitar colisión namespace
	@printf "$(CYAN)→ Suite principal (tests/)$(RESET)\n"
	$(PYTEST) -x --tb=short tests/
	@printf "$(CYAN)→ Suite SDK (sdk/python/tests/)$(RESET)\n"
	$(PYTEST) -x --tb=short sdk/python/tests/

test-unit: ## Tests unitarios (excluye tests/e2e/)
	$(PYTEST) -x --tb=short tests/ --ignore=tests/e2e

test-e2e: ## Tests E2E con mocks respx (tests/e2e/)
	$(PYTEST) -x --tb=short tests/e2e/

test-sdk: ## Tests del SDK Python (sdk/python/tests/)
	$(PYTEST) -x --tb=short sdk/python/tests/

test-fast: ## Tests en paralelo, sin cobertura (requiere pytest-xdist)
	$(PYTEST) -n auto --tb=short tests/

cov: ## Cobertura gate = 41% (medido 43%, objetivo v0.2 = 45%, ver docs/COVERAGE_ROADMAP.md)
	$(PYTEST) --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=41 tests/ sdk/python/tests/
	@printf "$(GREEN)✓ Reporte HTML en $(BOLD)htmlcov/index.html$(RESET)\n"
	@printf "$(YELLOW)Nota:$(RESET) gate 41%% (medido 43%%). Objetivo v0.2 = 45%%. Ver $(BOLD)docs/COVERAGE_ROADMAP.md$(RESET)\n"

verify: lint typecheck test cov ## Suite completa pre-commit: lint + typecheck + test + cov
	@printf "$(GREEN)$(BOLD)✓ Verify completo: todo OK$(RESET)\n"

# =============================================================================
# CALIDAD DE CÓDIGO
# =============================================================================

lint: ## Linter Ruff sobre app/ sdk/ tests/
	$(RUFF) check app/ sdk/ tests/

format: ## Formateo automático: Black + Ruff --fix
	$(BLACK) app/ sdk/ tests/
	$(RUFF) check --fix app/ sdk/ tests/
	@printf "$(GREEN)✓ Código formateado$(RESET)\n"

typecheck: ## Type checking MyPy sobre app/
	$(MYPY) app/

rebrand-verify: ## Verifica que no quedan strings IDM-CORE/IDMMORTALITY residuales (DoD §7)
	@printf "$(CYAN)→ Buscando residuos del rebrand vital-core → Micelia...$(RESET)\n"
	@hits=$$(grep -rEn "IDM-CORE|IDMMORTALITY" \
		--include="*.py" --include="*.ts" --include="*.tsx" \
		--exclude-dir=".venv" --exclude-dir="node_modules" --exclude-dir="__pycache__" \
		--exclude-dir="docs" \
		. 2>/dev/null); \
	if [ -z "$$hits" ]; then \
		printf "$(GREEN)✓ Sin residuos en código (docs/ excluido legítimamente)$(RESET)\n"; \
	else \
		printf "$(RED)✗ Hits residuales encontrados:$(RESET)\n"; \
		printf "%s\n" "$$hits"; \
		exit 1; \
	fi

# =============================================================================
# EJECUCIÓN LOCAL
# =============================================================================

_dev-banner: ## (interno) imprime el panel de URLs y puertos del ecosistema
	@printf "\n"
	@printf "$(BOLD)$(CYAN)╔═══════════════════════════════════════════════════════════════════════╗$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)  $(BOLD)Micelia$(RESET) — Orquestador del ecosistema UTOP.IA                       $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)╠═══════════════════════════════════════════════════════════════════════╣$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)                                                                       $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)  $(BOLD)$(GREEN)Gateway Micelia$(RESET)                                                      $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    Root        $(YELLOW)http://localhost:8888$(RESET)                                  $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    Swagger UI  $(YELLOW)http://localhost:8888/docs$(RESET)                             $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    ReDoc       $(YELLOW)http://localhost:8888/redoc$(RESET)                            $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    Metrics     $(YELLOW)http://localhost:8888/metrics$(RESET)                          $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)                                                                       $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)  $(BOLD)$(GREEN)Frontend$(RESET)        $(YELLOW)http://localhost:3001$(RESET)  $(BOLD)(make frontend-dev)$(RESET)         $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)                                                                       $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)  $(BOLD)$(GREEN)Subservicios$(RESET) (activar con $(BOLD)make docker-health$(RESET) o $(BOLD)docker-full$(RESET))           $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    biohack-app    $(YELLOW)http://localhost:8081$(RESET)   salud         $(BOLD)docker-health$(RESET)  $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    canela-molida  $(YELLOW)http://localhost:3690$(RESET)   investigación $(BOLD)docker-full$(RESET)    $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    ideacursi      $(YELLOW)http://localhost:5050$(RESET)   educación     $(BOLD)docker-full$(RESET)    $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    cybertools     $(YELLOW)http://localhost:8000$(RESET)   seguridad     $(BOLD)docker-full$(RESET)    $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    auto-mat-ion   $(YELLOW)http://localhost:3000$(RESET)   automatización $(BOLD)docker-full$(RESET)   $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)                                                                       $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)  $(BOLD)$(GREEN)Infraestructura$(RESET)                                                      $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    Postgres       $(YELLOW)localhost:5432$(RESET)          (idm-postgres)              $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    Redis          $(YELLOW)localhost:6379$(RESET)          (idm-redis)                 $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    Ollama         $(YELLOW)http://localhost:11434$(RESET)  (idm-ollama)                $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    Prometheus     $(YELLOW)http://localhost:9090$(RESET)   (profile: monitoring)       $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)    Grafana        $(YELLOW)http://localhost:3000$(RESET)   (profile: monitoring)       $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)║$(RESET)                                                                       $(BOLD)$(CYAN)║$(RESET)\n"
	@printf "$(BOLD)$(CYAN)╚═══════════════════════════════════════════════════════════════════════╝$(RESET)\n"
	@if [ "$(VERBOSE)" = "1" ]; then \
		printf "\n$(YELLOW)⚙ Modo verbose:$(RESET) --log-level debug + access-log activado\n"; \
	else \
		printf "\n$(GREEN)✓ Modo silencioso$(RESET) (warnings y errores). Logs detallados con $(BOLD)make dev-verbose$(RESET) o $(BOLD)VERBOSE=1 make dev$(RESET)\n"; \
	fi
	@printf "\n"

dev: _check-port-8888 _check-infra _dev-banner ## Arranca Micelia con resumen de puertos (silencioso; usa VERBOSE=1 para logs detallados)
	LOG_LEVEL=$(DEV_LOG_LEVEL) $(MICELIA) start --reload $(DEV_LOG_FLAGS)

dev-verbose: ## Arranca Micelia con logs detallados (equivalente a VERBOSE=1 make dev)
	@$(MAKE) dev VERBOSE=1

dev-idm: ## Arranca usando el CLI legacy `idm` (verifica DeprecationWarning)
	@printf "$(YELLOW)⚠ Usando CLI deprecado `idm`. Usa `make dev` (micelia) en su lugar.$(RESET)\n"
	LOG_LEVEL=$(DEV_LOG_LEVEL) $(IDM) start --reload $(DEV_LOG_FLAGS)

frontend-install: ## Instala dependencias npm del frontend Next.js
	cd $(FRONTEND_DIR) && npm install

frontend-dev: ## Arranca el frontend Next.js en modo dev (http://localhost:3001)
	@printf "$(CYAN)→ Arrancando frontend Next.js en :3001$(RESET)\n"
	cd $(FRONTEND_DIR) && npm run dev

frontend-dev-mock: ## Arranca el frontend con backend mockeado vía MSW (T4.1/T4.2 QA)
	@printf "$(CYAN)→ Arrancando frontend en modo MOCK (MSW intercepta /api/v1/*)$(RESET)\n"
	@if [ ! -f $(FRONTEND_DIR)/public/mockServiceWorker.js ]; then \
		printf "$(YELLOW)⚠ public/mockServiceWorker.js no existe. Ejecutando msw init...$(RESET)\n"; \
		cd $(FRONTEND_DIR) && npm run msw:init; \
	fi
	cd $(FRONTEND_DIR) && npm run dev:mock

frontend-build: ## Build de producción del frontend
	cd $(FRONTEND_DIR) && npm run build

frontend-lint: ## Lint + type-check del frontend
	cd $(FRONTEND_DIR) && npm run lint && npm run type-check

# =============================================================================
# DOCKER / INFRAESTRUCTURA
# =============================================================================

docker-infra: ## Levanta SOLO postgres + redis + ollama (mínimo para dev local)
	podman-compose up -d postgres redis ollama
	@printf "$(GREEN)✓ Infra arriba. Estado: $(BOLD)make docker-ps$(RESET)\n"

docker-up: ## Levanta gateway Micelia + infra (perfil default)
	podman-compose up -d

docker-full: ## Levanta el ecosistema completo (--profile full)
	podman-compose --profile full up -d

docker-monitoring: ## Añade Prometheus + Grafana (--profile monitoring)
	podman-compose --profile monitoring up -d

docker-health: ## Levanta + biohack-app (--profile health) — dominio salud
	podman-compose --profile health up -d

docker-down: ## Detiene y elimina todos los contenedores
	podman-compose down

docker-logs: ## Tail de logs del gateway (intenta micelia-core, fallback idm-core)
	@podman-compose logs -f micelia-core 2>/dev/null || podman-compose logs -f idm-core

docker-ps: ## Estado actual de los contenedores del stack
	podman-compose ps

# =============================================================================
# MANTENIMIENTO
# =============================================================================

clean: ## Limpia caches de Python (pycache, pytest, mypy, ruff, coverage)
	@find . -type d -name "__pycache__" -not -path "*/\.venv/*" -not -path "*/node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	@printf "$(GREEN)✓ Caches limpios$(RESET)\n"

clean-all: clean ## Limpia caches + venv + node_modules del frontend
	@rm -rf $(VENV)
	@rm -rf $(FRONTEND_DIR)/node_modules $(FRONTEND_DIR)/.next $(FRONTEND_DIR)/tsconfig.tsbuildinfo
	@printf "$(GREEN)✓ Reset total. Para reinstalar: $(BOLD)make setup$(RESET)\n"

version: ## Muestra gestor, versión de Python, Micelia y dependencias clave
	@printf "$(BOLD)$(CYAN)Versiones Micelia$(RESET)\n"
	@printf "Gestor:  $(BOLD)$(PKG_MGR_NAME)$(RESET)"
	@if [ -n "$(UV)" ]; then printf " ("; uv --version; printf ")"; fi
	@printf "\n"
	@$(BIN)/python --version 2>/dev/null || printf "$(RED)venv no instalado. Corre $(BOLD)make install$(RESET)\n"
	@$(MICELIA) --version 2>/dev/null || printf "$(RED)micelia CLI no disponible$(RESET)\n"
	@printf "\n$(BOLD)Dependencias clave:$(RESET)\n"
	@if [ -n "$(UV)" ]; then \
		uv pip list --python $(VENV) 2>/dev/null | grep -E "^(fastapi|httpx|respx|pytest|pydantic|sqlalchemy|click|rich)\s" || true; \
	else \
		$(BIN)/pip list 2>/dev/null | grep -E "^(fastapi|httpx|respx|pytest|pydantic|sqlalchemy|click|rich)\s" || true; \
	fi
