# Implementation Plan: Project Restructure

## Overview

Reorganize the Bot EV+ project from a flat structure into a modular `src/` package structure. The implementation follows a bottom-up approach: create the package structure, move files into their target packages, update all imports to absolute paths, fix path resolution, update Docker configuration, create entrypoint wrappers, and verify everything works.

## Tasks

- [x] 1. Create the `src/` package structure with `__init__.py` files
  - Create `src/__init__.py` (empty or minimal)
  - Create `src/core/__init__.py` with re-exports for `get_db`, `Database`, `FEED_ID`, `BASE_PATH`, `feed_path`, `get_logger`
  - Create `src/api/__init__.py` with re-exports for API-related symbols
  - Create `src/bot/__init__.py` with re-exports for bot-related symbols
  - Create `src/scanner/__init__.py` with re-exports for scanner-related symbols
  - Create `src/filters/__init__.py` with re-exports for `evento_valido`, `aplicar_filtros_dinamicos`, `validar_filtros_usuario`, `usuario_configurado`
  - Create `src/data/__init__.py` with re-exports for `get_cache`, `get_history`, `get_user_manager`
  - Create `src/utils/__init__.py` with re-exports for `formatar_ev`, `formatar_odd`, `formatar_stake`, `logger_geral`, `logger_scan`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 2. Move core modules into `src/core/` and update their internal imports
  - [x] 2.1 Move `config.py` to `src/core/config.py` and update `BASE_PATH` to navigate up 2 levels (`os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`)
    - Ensure `BASE_PATH` resolves to project root after the move
    - All path functions (`feed_path`, `get_database_path`, `get_listener_log_path`) must still resolve relative to project root
    - _Requirements: 1.2, 4.1, 4.2, 4.3_

  - [x] 2.2 Move `logging_config.py` to `src/core/logging_config.py` and update its imports
    - Update `from config import FEED_ID, BASE_PATH` → `from src.core.config import FEED_ID, BASE_PATH`
    - _Requirements: 1.2, 2.1, 2.2_

  - [x] 2.3 Move `database.py` to `src/core/database.py` and update its imports
    - Update `from config import feed_path, FEED_ID` → `from src.core.config import feed_path, FEED_ID`
    - _Requirements: 1.2, 2.1, 2.2_

- [ ] 3. Move API modules into `src/api/` and update their internal imports
  - [x] 3.1 Move `api_client.py` to `src/api/api_client.py` and update all imports
    - Update imports from `config`, `database`, `metrics`, `rate_limiter_global`, `logging_config`, `messages`
    - Preserve `OddsAPIClient = OddsAPI` alias
    - _Requirements: 1.3, 2.1, 2.2, 2.4_

  - [x] 3.2 Move `rate_limiter.py` to `src/api/rate_limiter.py` and update its imports
    - _Requirements: 1.3, 2.1, 2.2_

  - [x] 3.3 Move `rate_limiter_global.py` to `src/api/rate_limiter_global.py` and update its imports
    - _Requirements: 1.3, 2.1, 2.2_

  - [x] 3.4 Move `status.py` to `src/api/status.py` and update its imports
    - _Requirements: 1.3, 2.1, 2.2_

- [ ] 4. Move filter modules into `src/filters/` and update their internal imports
  - [x] 4.1 Move `filtros.py` to `src/filters/filtros.py` and update its imports
    - _Requirements: 1.6, 2.1, 2.2_

  - [x] 4.2 Move `bookmaker_config.py` to `src/filters/bookmaker_config.py` and update its imports
    - Update `from database import get_db` → `from src.core.database import get_db`
    - _Requirements: 1.6, 2.1, 2.2_

- [ ] 5. Move data modules into `src/data/` and update their internal imports
  - [x] 5.1 Move `cache.py` to `src/data/cache.py` and update its imports
    - Update `from database import get_db, generate_alert_hash` → `from src.core.database import get_db, generate_alert_hash`
    - _Requirements: 1.7, 2.1, 2.2_

  - [x] 5.2 Move `historico.py` to `src/data/historico.py` and update its imports
    - Update `from database import get_db, generate_alert_hash` → `from src.core.database import get_db, generate_alert_hash`
    - _Requirements: 1.7, 2.1, 2.2_

  - [x] 5.3 Move `usuarios.py` to `src/data/usuarios.py` and update its imports
    - _Requirements: 1.7, 2.1, 2.2_

- [ ] 6. Move utility modules into `src/utils/` and update their internal imports
  - [x] 6.1 Move `formatadores.py` to `src/utils/formatadores.py` and update its imports
    - _Requirements: 1.8, 2.1, 2.2_

  - [x] 6.2 Move `messages.py` to `src/utils/messages.py` and update its imports
    - _Requirements: 1.8, 2.1, 2.2_

  - [x] 6.3 Move `metrics.py` to `src/utils/metrics.py` and update its imports
    - _Requirements: 1.8, 2.1, 2.2_

  - [x] 6.4 Move `utils.py` to `src/utils/utils.py` and update its imports
    - Update imports from `database`, `logging_config`
    - _Requirements: 1.8, 2.1, 2.2_

- [x] 7. Checkpoint - Verify foundational modules
  - Ensure all modules in `src/core/`, `src/api/`, `src/filters/`, `src/data/`, `src/utils/` can be imported without errors
  - Run `python -c "from src.core.config import BASE_PATH; import os; assert os.path.isfile(os.path.join(BASE_PATH, 'Dockerfile'))"`
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Move bot modules into `src/bot/` and update their internal imports
  - [x] 8.1 Move `bot_core.py` to `src/bot/bot_core.py` and update its imports
    - _Requirements: 1.4, 2.1, 2.2_

  - [x] 8.2 Move `bot_ev.py` to `src/bot/bot_ev.py` and update its imports
    - Update imports from `config`, `database`, `bot_core`, `formatadores`
    - _Requirements: 1.4, 2.1, 2.2_

  - [x] 8.3 Move `bot_listener.py` to `src/bot/bot_listener.py` and update its imports
    - Update all imports: `api_client`, `bookmaker_config`, `config`, `database`, `rate_limiter`, `scanner`, `status`, `utils`, `logging_config`
    - _Requirements: 1.4, 2.1, 2.2, 2.3_

- [ ] 9. Move scanner modules into `src/scanner/` and update their internal imports
  - [x] 9.1 Move `scanner.py` to `src/scanner/scanner.py` and update its imports
    - _Requirements: 1.5, 2.1, 2.2_

  - [x] 9.2 Move `scan_cache.py` to `src/scanner/scan_cache.py` and update its imports
    - Ensure `os.getcwd()` based paths still resolve correctly
    - _Requirements: 1.5, 2.1, 2.2, 4.4_

  - [x] 9.3 Move `global_scanner.py` to `src/scanner/global_scanner.py` and update its imports
    - Update imports from `config`, `database`, `api_client`, `rate_limiter_global`, `utils`, `logging_config`, `metrics`, `scan_cache`
    - Preserve `main()` function as the entrypoint target
    - _Requirements: 1.5, 2.1, 2.2, 2.3_

  - [x] 9.4 Move `main_scheduler.py` to `src/scanner/main_scheduler.py` and update its imports
    - Update all imports: `config`, `database`, `usuarios`, `cache`, `historico`, `status`, `rate_limiter`, `filtros`, `bot_core`, `bot_ev`, `utils`, `scan_cache`, `messages`, `metrics`
    - Preserve lazy/local imports (e.g., `from bot_ev import enviar_alerta_instantaneo` inside `_processar_usuario`) to avoid circular dependencies
    - Preserve `main()` function as the entrypoint target
    - _Requirements: 1.5, 2.1, 2.2, 2.3_

- [x] 10. Checkpoint - Verify all src modules import correctly
  - Run import verification for all 23 modules listed in the design document
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Create thin entrypoint wrappers at project root
  - [x] 11.1 Replace root `global_scanner.py` with a thin wrapper that delegates to `src.scanner.global_scanner.main`
    - Add `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` for path resolution
    - Preserve `if __name__ == "__main__"` block with `asyncio.run(main())`
    - _Requirements: 3.1, 3.2, 3.6_

  - [x] 11.2 Replace root `main_scheduler.py` with a thin wrapper that delegates to `src.scanner.main_scheduler.main`
    - _Requirements: 3.1, 3.3, 3.6_

  - [x] 11.3 Replace root `bot_listener.py` with a thin wrapper that delegates to `src.bot.bot_listener`
    - Must run the Telegram bot application (not just import)
    - _Requirements: 3.1, 3.4, 3.6_

  - [x] 11.4 Replace root `init_database.py` with a thin wrapper that delegates to `src.core.database`
    - _Requirements: 7.1, 7.2_

  - [x] 11.5 Replace root `web_dashboard.py` with a thin wrapper (if it exists as a full module)
    - _Requirements: 3.1_

- [ ] 12. Update Docker configuration
  - [x] 12.1 Update `Dockerfile` COPY instructions to include `src/` directory
    - Change `COPY . .` to explicit copies: `COPY src/ ./src/`, `COPY *.py ./`, `COPY requirements.txt .`, etc.
    - Ensure WORKDIR `/app` still contains all necessary files
    - _Requirements: 5.1, 5.2_

  - [x] 12.2 Update `docker-entrypoint.sh` inline Python imports
    - Update `from database import get_db` → `from src.core.database import get_db`
    - Update `from global_scanner import GlobalScanner` → `from src.scanner.global_scanner import GlobalScanner`
    - Update `from main_scheduler import BotScheduler` → `from src.scanner.main_scheduler import BotScheduler`
    - Update `from scan_cache import get_snapshot_cache` → `from src.scanner.scan_cache import get_snapshot_cache`
    - Verify that `python global_scanner.py`, `python main_scheduler.py`, `python bot_listener.py` commands still work via thin wrappers
    - _Requirements: 5.4, 3.5_

- [x] 13. Clean up old files from project root
  - Remove the original Python source files from the project root that have been moved to `src/` (config.py, database.py, logging_config.py, api_client.py, rate_limiter.py, rate_limiter_global.py, status.py, bot_core.py, bot_ev.py, bot_listener_original_content, filtros.py, bookmaker_config.py, cache.py, historico.py, usuarios.py, formatadores.py, messages.py, metrics.py, utils.py, scanner.py, scan_cache.py, global_scanner_original_content, main_scheduler_original_content)
  - Keep only the thin entrypoint wrappers at root
  - Remove `__pycache__/` directories from root
  - _Requirements: 1.1_

- [ ] 14. Final verification and smoke tests
  - [x] 14.1 Create and run the import verification script from the design document
    - Verify all 23 `src.*` modules can be imported without ImportError
    - _Requirements: 8.1_

  - [x] 14.2 Verify entrypoint wrappers execute their import phase successfully
    - Run `python -c "import importlib.util; spec = importlib.util.spec_from_file_location('ep', 'global_scanner.py')"` for each entrypoint
    - _Requirements: 8.2_

  - [x] 14.3 Verify path resolution
    - Assert `BASE_PATH` points to project root (contains `Dockerfile`, `data/`, `logs/`, `src/`)
    - Assert `feed_path("bot.db", "default")` resolves to `data/default/bot.db`
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 14.4 Verify Docker build succeeds
    - Run `docker build -t bot-ev-test .`
    - Run `docker run --rm bot-ev-test test` to verify module imports inside container
    - _Requirements: 5.1, 5.2, 5.3, 8.3_

- [x] 15. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- No tasks are marked optional since this is a structural migration where all steps are required for correctness
- Property-based testing is not applicable for this one-time migration (as stated in the design)
- Lazy/local imports (used to break circular dependencies) must be preserved during the move — only their paths change
- The `data/` and `logs/` directories remain at the project root and are NOT moved
- `docker-compose.yml` requires no changes since volume mounts and commands remain the same
- Each task builds on previous tasks — modules must be moved in dependency order (core first, then modules that depend on core)
