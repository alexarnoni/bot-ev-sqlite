# Requirements Document

## Introduction

Reorganização da estrutura do projeto Bot EV+ de uma estrutura flat (todos os arquivos Python no diretório raiz) para uma estrutura modular organizada em pacotes Python. O objetivo é melhorar a manutenibilidade, legibilidade e escalabilidade do projeto, garantindo que todos os imports continuem funcionando corretamente após a migração.

## Glossary

- **Project_Root**: Diretório raiz do repositório onde residem os arquivos de configuração (Dockerfile, docker-compose.yml, .env)
- **Package**: Diretório Python contendo um arquivo `__init__.py` que agrupa módulos relacionados
- **Module**: Arquivo Python individual (.py) contendo código fonte
- **Import_Statement**: Declaração Python que referencia código de outro módulo (ex: `from config import FEED_ID`)
- **Entrypoint**: Módulo Python executado diretamente como script principal (ex: `main_scheduler.py`, `global_scanner.py`, `bot_listener.py`)
- **Internal_Import**: Import entre módulos do próprio projeto (não bibliotecas externas)
- **Restructuring_Tool**: Sistema responsável por mover arquivos e atualizar imports

## Requirements

### Requirement 1: Organização em Pacotes por Domínio

**User Story:** As a developer, I want the Python source files organized into domain-specific packages, so that I can find and maintain related code more easily.

#### Acceptance Criteria

1. THE Restructuring_Tool SHALL create a `src/` top-level package containing all application source code
2. THE Restructuring_Tool SHALL create a `src/core/` package containing foundational modules (config, logging_config, database)
3. THE Restructuring_Tool SHALL create a `src/api/` package containing API client and rate limiting modules (api_client, rate_limiter, rate_limiter_global, status)
4. THE Restructuring_Tool SHALL create a `src/bot/` package containing Telegram bot modules (bot_listener, bot_ev, bot_core)
5. THE Restructuring_Tool SHALL create a `src/scanner/` package containing scanning modules (global_scanner, main_scheduler, scanner, scan_cache)
6. THE Restructuring_Tool SHALL create a `src/filters/` package containing filtering and validation modules (filtros, bookmaker_config)
7. THE Restructuring_Tool SHALL create a `src/data/` package containing data management modules (cache, historico, usuarios)
8. THE Restructuring_Tool SHALL create a `src/utils/` package containing utility modules (formatadores, messages, metrics, utils)
9. WHEN a package is created, THE Restructuring_Tool SHALL include an `__init__.py` file that re-exports the package's public API

### Requirement 2: Preservação de Imports Internos

**User Story:** As a developer, I want all internal imports to work correctly after restructuring, so that the application continues to function without errors.

#### Acceptance Criteria

1. WHEN a module is moved to a new package, THE Restructuring_Tool SHALL update all Internal_Import statements that reference that module across the entire codebase
2. WHEN a module imports from another module using `from X import Y`, THE Restructuring_Tool SHALL update the import path to reflect the new package location
3. WHEN a module imports using `import X`, THE Restructuring_Tool SHALL update the import to use the new fully-qualified package path
4. THE Restructuring_Tool SHALL preserve all existing import aliases (e.g., `OddsAPIClient = OddsAPI`)
5. IF an import path cannot be resolved after restructuring, THEN THE Restructuring_Tool SHALL report the unresolved import as an error

### Requirement 3: Preservação de Entrypoints

**User Story:** As a developer, I want the application entrypoints to remain accessible from the project root, so that Docker and shell scripts continue to work.

#### Acceptance Criteria

1. THE Restructuring_Tool SHALL maintain thin entrypoint scripts in the Project_Root that delegate to the actual module implementations inside `src/`
2. WHEN the Dockerfile references `python global_scanner.py`, THE Restructuring_Tool SHALL ensure this command continues to work after restructuring
3. WHEN the Dockerfile references `python main_scheduler.py`, THE Restructuring_Tool SHALL ensure this command continues to work after restructuring
4. WHEN the Dockerfile references `python bot_listener.py`, THE Restructuring_Tool SHALL ensure this command continues to work after restructuring
5. WHEN docker-entrypoint.sh references a Python module, THE Restructuring_Tool SHALL update the reference to work with the new structure
6. THE Restructuring_Tool SHALL preserve the `if __name__ == "__main__"` blocks in entrypoint modules

### Requirement 4: Preservação de Paths Relativos

**User Story:** As a developer, I want file path calculations (data directories, log directories) to continue resolving correctly, so that runtime data is stored in the expected locations.

#### Acceptance Criteria

1. WHEN `config.py` uses `os.path.dirname(os.path.abspath(__file__))` for BASE_PATH, THE Restructuring_Tool SHALL ensure BASE_PATH still resolves to the Project_Root
2. WHEN modules reference `data/` or `logs/` directories, THE Restructuring_Tool SHALL ensure these paths resolve relative to the Project_Root
3. THE Restructuring_Tool SHALL update the `BASE_PATH` calculation in config.py to account for the new directory depth
4. WHEN `scan_cache.py` uses `os.getcwd()` for database paths, THE Restructuring_Tool SHALL ensure the path resolves correctly regardless of the module's new location

### Requirement 5: Compatibilidade com Docker

**User Story:** As a developer, I want the Docker configuration to work without changes to the container behavior, so that deployments are not disrupted.

#### Acceptance Criteria

1. THE Restructuring_Tool SHALL update the Dockerfile COPY instructions to include the new `src/` directory structure
2. THE Restructuring_Tool SHALL ensure the WORKDIR `/app` in Docker still contains all necessary files
3. WHEN docker-compose.yml mounts volumes, THE Restructuring_Tool SHALL ensure data and logs directories remain accessible at the expected paths
4. THE Restructuring_Tool SHALL update docker-entrypoint.sh to reference the correct module paths after restructuring

### Requirement 6: Pacote __init__.py com Re-exports

**User Story:** As a developer, I want each package's `__init__.py` to re-export key symbols, so that existing import patterns can optionally still work with shorter paths.

#### Acceptance Criteria

1. WHEN a package `__init__.py` is created, THE Restructuring_Tool SHALL include imports of the package's primary public functions and classes
2. THE `src/core/__init__.py` SHALL re-export `get_db`, `Database`, `FEED_ID`, `BASE_PATH`, `feed_path`, `get_logger`
3. THE `src/filters/__init__.py` SHALL re-export `evento_valido`, `aplicar_filtros_dinamicos`, `validar_filtros_usuario`
4. THE `src/data/__init__.py` SHALL re-export `get_cache`, `get_history`, `get_user_manager`
5. THE `src/utils/__init__.py` SHALL re-export `formatar_ev`, `formatar_odd`, `formatar_stake`, `logger_geral`, `logger_scan`

### Requirement 7: Arquivo init_database.py como Script de Manutenção

**User Story:** As a developer, I want the database initialization script to remain easily runnable, so that I can initialize databases when needed.

#### Acceptance Criteria

1. THE Restructuring_Tool SHALL keep `init_database.py` accessible as a runnable script from the Project_Root
2. WHEN `init_database.py` imports from `database` and `config`, THE Restructuring_Tool SHALL update these imports to use the new package paths

### Requirement 8: Verificação Pós-Reestruturação

**User Story:** As a developer, I want to verify that the restructured project has no broken imports, so that I can be confident the migration was successful.

#### Acceptance Criteria

1. WHEN the restructuring is complete, THE Restructuring_Tool SHALL verify that all Python files can be imported without ImportError
2. WHEN the restructuring is complete, THE Restructuring_Tool SHALL verify that all entrypoint scripts execute their import phase successfully
3. IF a circular import is detected after restructuring, THEN THE Restructuring_Tool SHALL resolve it by using lazy imports or restructuring the dependency
