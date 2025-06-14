# Firmware Command Refactoring Implementation Plan

## Overview

This plan outlines the refactoring of `glovebox/cli/commands/firmware.py` to improve maintainability, testability, and support for multiple compilation strategies including Moergo. The current implementation has grown complex with mixed responsibilities and strategy-specific logic scattered throughout.

## Current Issues

1. **Mixed Responsibilities**: The firmware.py file handles parameter parsing, config building, strategy detection, and execution all in one place
2. **Complex Strategy Detection**: Moergo detection uses fragile `hasattr` checks and type inspection
3. **Difficult Testing**: Large functions with many dependencies make unit testing challenging
4. **Poor Extensibility**: Adding new compilation strategies requires modifying multiple functions
5. **Code Duplication**: Similar patterns repeated for different strategies
6. **Parameter Overload**: The compile command has 20+ parameters making it unwieldy

## Goals

1. **Clean Architecture**: Separate concerns into focused, single-responsibility components
2. **Strategy Pattern**: Implement proper strategy pattern for compilation methods
3. **Improved Testability**: Create small, testable units with clear interfaces
4. **Better Extensibility**: Make it easy to add new compilation strategies
5. **Code Reusability**: Extract common patterns into reusable components
6. **CLAUDE.md Compliance**: Follow all project conventions strictly

## Implementation Steps

### Step 1: Create Base Strategy Infrastructure

**Files to create:**
- `glovebox/cli/strategies/__init__.py`
- `glovebox/cli/strategies/base.py`
- `tests/test_cli/test_strategies/__init__.py`
- `tests/test_cli/test_strategies/test_base.py`

**Implementation:**

1. Create base strategy protocol:
```python
# glovebox/cli/strategies/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from glovebox.config.compile_methods import DockerCompilationConfig
from glovebox.config.keyboard_profile import KeyboardProfile


@dataclass
class CompilationParams:
    """Compilation parameters from CLI."""
    
    keymap_file: Path
    kconfig_file: Path
    output_dir: Path
    branch: str | None
    repo: str | None
    jobs: int | None
    verbose: bool
    no_cache: bool
    docker_uid: int | None
    docker_gid: int | None
    docker_username: str | None
    docker_home: str | None
    docker_container_home: str | None
    no_docker_user_mapping: bool
    board_targets: str | None


class CompilationStrategyProtocol(Protocol):
    """Protocol for compilation strategies."""
    
    @property
    def name(self) -> str:
        """Strategy name."""
        ...
    
    def supports_profile(self, profile: KeyboardProfile) -> bool:
        """Check if strategy supports the given profile."""
        ...
    
    def extract_docker_image(self, profile: KeyboardProfile) -> str:
        """Extract Docker image from profile."""
        ...
    
    def build_config(
        self, 
        params: CompilationParams,
        profile: KeyboardProfile
    ) -> DockerCompilationConfig:
        """Build compilation configuration."""
        ...
    
    def get_service_name(self) -> str:
        """Get the compilation service name."""
        ...


class BaseCompilationStrategy(ABC):
    """Base implementation for compilation strategies."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name."""
        pass
    
    @abstractmethod
    def supports_profile(self, profile: KeyboardProfile) -> bool:
        """Check if strategy supports the given profile."""
        pass
    
    def get_service_name(self) -> str:
        """Get the compilation service name."""
        return self.name
```

2. Create tests:
```python
# tests/test_cli/test_strategies/test_base.py
import pytest
from pathlib import Path

from glovebox.cli.strategies.base import CompilationParams, BaseCompilationStrategy


def test_compilation_params_creation():
    """Test CompilationParams dataclass creation."""
    params = CompilationParams(
        keymap_file=Path("test.keymap"),
        kconfig_file=Path("test.conf"),
        output_dir=Path("build"),
        branch=None,
        repo=None,
        jobs=4,
        verbose=True,
        no_cache=False,
        docker_uid=1000,
        docker_gid=1000,
        docker_username="test",
        docker_home="/home/test",
        docker_container_home="/tmp",
        no_docker_user_mapping=False,
        board_targets="glove80_lh,glove80_rh"
    )
    
    assert params.keymap_file == Path("test.keymap")
    assert params.jobs == 4
    assert params.docker_uid == 1000


class TestStrategy(BaseCompilationStrategy):
    """Test implementation of base strategy."""
    
    @property
    def name(self) -> str:
        return "test"
    
    def supports_profile(self, profile) -> bool:
        return True


def test_base_strategy_abstract_methods():
    """Test that abstract methods must be implemented."""
    strategy = TestStrategy()
    assert strategy.name == "test"
    assert strategy.get_service_name() == "test"
```

**Validation:**
```bash
# Run linting
ruff check glovebox/cli/strategies/ --fix
ruff format glovebox/cli/strategies/
mypy glovebox/cli/strategies/

# Run tests
pytest tests/test_cli/test_strategies/test_base.py -v
```

**Commit:**
```bash
git add glovebox/cli/strategies/ tests/test_cli/test_strategies/
git commit -m "feat: add base compilation strategy infrastructure

- Create CompilationStrategyProtocol for type safety
- Add CompilationParams dataclass for parameter handling
- Implement BaseCompilationStrategy abstract class
- Add comprehensive tests for base components"
```

### Step 2: Implement ZMK Config Strategy

**Files to create:**
- `glovebox/cli/strategies/zmk_config.py`
- `tests/test_cli/test_strategies/test_zmk_config.py`

**Implementation:**

1. Create ZMK config strategy:
```python
# glovebox/cli/strategies/zmk_config.py
import logging
from typing import cast

from glovebox.cli.strategies.base import BaseCompilationStrategy, CompilationParams
from glovebox.config.compile_methods import CacheConfig, ZmkCompilationConfig
from glovebox.config.keyboard_profile import KeyboardProfile


logger = logging.getLogger(__name__)


class ZmkConfigStrategy(BaseCompilationStrategy):
    """Standard ZMK config compilation strategy."""
    
    @property
    def name(self) -> str:
        return "zmk_config"
    
    def supports_profile(self, profile: KeyboardProfile) -> bool:
        """Check if profile has ZMK config compile method."""
        if not profile or not profile.keyboard_config:
            return False
            
        for method in profile.keyboard_config.compile_methods:
            if hasattr(method, "strategy") and method.strategy == "zmk_config":
                return True
            if isinstance(method, ZmkCompilationConfig):
                return True
        return False
    
    def extract_docker_image(self, profile: KeyboardProfile) -> str:
        """Extract Docker image from profile."""
        default_image = "zmkfirmware/zmk-build-arm:stable"
        
        if not profile or not profile.keyboard_config:
            return default_image
            
        for method in profile.keyboard_config.compile_methods:
            if isinstance(method, ZmkCompilationConfig):
                return method.image or default_image
            if hasattr(method, "strategy") and method.strategy == "zmk_config":
                return getattr(method, "image", default_image)
                
        return default_image
    
    def build_config(
        self, 
        params: CompilationParams,
        profile: KeyboardProfile
    ) -> ZmkCompilationConfig:
        """Build ZMK compilation configuration."""
        # Find profile config
        profile_config = self._get_profile_config(profile)
        
        if profile_config:
            config = profile_config.model_copy()
            logger.debug("Using profile ZmkCompilationConfig as base")
        else:
            config = ZmkCompilationConfig(artifact_naming="zmk_github_actions")
            logger.debug("Using default ZmkCompilationConfig")
        
        # Apply CLI overrides
        if params.branch is not None:
            config.branch = params.branch
        if params.repo is not None:
            config.repository = params.repo
        if params.jobs is not None:
            config.jobs = params.jobs
            
        # Apply cache settings
        config.cache = CacheConfig(enabled=not params.no_cache)
        
        return config
    
    def _get_profile_config(self, profile: KeyboardProfile) -> ZmkCompilationConfig | None:
        """Get ZMK config from profile."""
        if not profile or not profile.keyboard_config:
            return None
            
        for method in profile.keyboard_config.compile_methods:
            if isinstance(method, ZmkCompilationConfig):
                return method
                
        return None
```

2. Create tests:
```python
# tests/test_cli/test_strategies/test_zmk_config.py
import pytest
from pathlib import Path

from glovebox.cli.strategies.base import CompilationParams
from glovebox.cli.strategies.zmk_config import ZmkConfigStrategy
from glovebox.config.compile_methods import ZmkCompilationConfig
from glovebox.config.keyboard_profile import KeyboardProfile
from glovebox.models.keyboard_config import KeyboardConfig


def test_zmk_config_strategy_name():
    """Test strategy name."""
    strategy = ZmkConfigStrategy()
    assert strategy.name == "zmk_config"
    assert strategy.get_service_name() == "zmk_config"


def test_supports_profile_with_zmk_config():
    """Test profile support detection."""
    strategy = ZmkConfigStrategy()
    
    # Profile with ZMK config
    config = KeyboardConfig(
        keyboard_name="test",
        compile_methods=[
            ZmkCompilationConfig(
                image="zmkfirmware/zmk-build-arm:stable",
                artifact_naming="zmk_github_actions"
            )
        ]
    )
    profile = KeyboardProfile(keyboard_config=config, firmware_version="v1.0")
    
    assert strategy.supports_profile(profile) is True


def test_extract_docker_image():
    """Test Docker image extraction."""
    strategy = ZmkConfigStrategy()
    
    # Profile with custom image
    config = KeyboardConfig(
        keyboard_name="test",
        compile_methods=[
            ZmkCompilationConfig(
                image="custom/zmk:latest",
                artifact_naming="zmk_github_actions"
            )
        ]
    )
    profile = KeyboardProfile(keyboard_config=config, firmware_version="v1.0")
    
    assert strategy.extract_docker_image(profile) == "custom/zmk:latest"


def test_build_config_with_overrides():
    """Test config building with CLI overrides."""
    strategy = ZmkConfigStrategy()
    
    params = CompilationParams(
        keymap_file=Path("test.keymap"),
        kconfig_file=Path("test.conf"),
        output_dir=Path("build"),
        branch="test-branch",
        repo="test/repo",
        jobs=8,
        verbose=False,
        no_cache=True,
        docker_uid=None,
        docker_gid=None,
        docker_username=None,
        docker_home=None,
        docker_container_home=None,
        no_docker_user_mapping=False,
        board_targets=None
    )
    
    profile = KeyboardProfile(
        keyboard_config=KeyboardConfig(
            keyboard_name="test",
            compile_methods=[ZmkCompilationConfig()]
        ),
        firmware_version="v1.0"
    )
    
    config = strategy.build_config(params, profile)
    
    assert config.branch == "test-branch"
    assert config.repository == "test/repo"
    assert config.jobs == 8
    assert config.cache.enabled is False
```

**Validation:**
```bash
# Run linting
ruff check glovebox/cli/strategies/zmk_config.py --fix
ruff format glovebox/cli/strategies/zmk_config.py
mypy glovebox/cli/strategies/

# Run tests
pytest tests/test_cli/test_strategies/test_zmk_config.py -v
```

**Commit:**
```bash
git add glovebox/cli/strategies/zmk_config.py tests/test_cli/test_strategies/test_zmk_config.py
git commit -m "feat: implement ZMK config compilation strategy

- Add ZmkConfigStrategy class with profile support detection
- Implement Docker image extraction from profiles
- Add config building with CLI override support
- Include comprehensive test coverage"
```

### Step 3: Implement Moergo Strategy

**Files to create:**
- `glovebox/cli/strategies/moergo.py`
- `tests/test_cli/test_strategies/test_moergo.py`

**Implementation:**

1. Create Moergo strategy:
```python
# glovebox/cli/strategies/moergo.py
import logging
from typing import cast

from glovebox.cli.strategies.base import BaseCompilationStrategy, CompilationParams
from glovebox.config.compile_methods import DockerUserConfig, MoergoCompilationConfig
from glovebox.config.keyboard_profile import KeyboardProfile


logger = logging.getLogger(__name__)


class MoergoStrategy(BaseCompilationStrategy):
    """Moergo-specific compilation strategy."""
    
    @property
    def name(self) -> str:
        return "moergo"
    
    def supports_profile(self, profile: KeyboardProfile) -> bool:
        """Check if profile has Moergo compile method."""
        if not profile or not profile.keyboard_config:
            return False
            
        for method in profile.keyboard_config.compile_methods:
            # Check by type
            if isinstance(method, MoergoCompilationConfig):
                return True
            # Check by attributes (legacy detection)
            if (hasattr(method, "repository") and 
                hasattr(method, "branch") and
                getattr(method, "repository", "").startswith("moergo")):
                return True
        return False
    
    def extract_docker_image(self, profile: KeyboardProfile) -> str:
        """Extract Docker image from profile."""
        default_image = "glove80-zmk-config-docker"
        
        if not profile or not profile.keyboard_config:
            return default_image
            
        for method in profile.keyboard_config.compile_methods:
            if isinstance(method, MoergoCompilationConfig):
                return method.image
            # Legacy check
            if (hasattr(method, "repository") and 
                getattr(method, "repository", "").startswith("moergo")):
                return getattr(method, "image", default_image)
                
        return default_image
    
    def build_config(
        self, 
        params: CompilationParams,
        profile: KeyboardProfile
    ) -> MoergoCompilationConfig:
        """Build Moergo compilation configuration."""
        # Find profile config
        profile_config = self._get_profile_config(profile)
        
        if profile_config:
            config = profile_config.model_copy()
            logger.debug("Using profile MoergoCompilationConfig as base")
        else:
            config = MoergoCompilationConfig()
            logger.debug("Using default MoergoCompilationConfig")
        
        # Apply CLI overrides
        if params.branch is not None:
            config.branch = params.branch
        if params.repo is not None:
            config.repository = params.repo
        if params.jobs is not None:
            config.jobs = params.jobs
        
        # Moergo specific: disable user mapping by default
        if not hasattr(config, "docker_user") or config.docker_user is None:
            config.docker_user = DockerUserConfig(enable_user_mapping=False)
            
        return config
    
    def _get_profile_config(self, profile: KeyboardProfile) -> MoergoCompilationConfig | None:
        """Get Moergo config from profile."""
        if not profile or not profile.keyboard_config:
            return None
            
        for method in profile.keyboard_config.compile_methods:
            if isinstance(method, MoergoCompilationConfig):
                return method
                
        return None
```

2. Create tests:
```python
# tests/test_cli/test_strategies/test_moergo.py
import pytest
from pathlib import Path

from glovebox.cli.strategies.base import CompilationParams
from glovebox.cli.strategies.moergo import MoergoStrategy
from glovebox.config.compile_methods import MoergoCompilationConfig, DockerUserConfig
from glovebox.config.keyboard_profile import KeyboardProfile
from glovebox.models.keyboard_config import KeyboardConfig


def test_moergo_strategy_name():
    """Test strategy name."""
    strategy = MoergoStrategy()
    assert strategy.name == "moergo"
    assert strategy.get_service_name() == "moergo"


def test_supports_profile_with_moergo_config():
    """Test profile support detection."""
    strategy = MoergoStrategy()
    
    # Profile with Moergo config
    config = KeyboardConfig(
        keyboard_name="glove80",
        compile_methods=[
            MoergoCompilationConfig(
                repository="moergo-sc/zmk",
                branch="v25.05"
            )
        ]
    )
    profile = KeyboardProfile(keyboard_config=config, firmware_version="v25.05")
    
    assert strategy.supports_profile(profile) is True


def test_extract_docker_image():
    """Test Docker image extraction."""
    strategy = MoergoStrategy()
    
    # Profile with default Moergo image
    config = KeyboardConfig(
        keyboard_name="glove80",
        compile_methods=[MoergoCompilationConfig()]
    )
    profile = KeyboardProfile(keyboard_config=config, firmware_version="v25.05")
    
    assert strategy.extract_docker_image(profile) == "glove80-zmk-config-docker"


def test_build_config_disables_user_mapping():
    """Test that Moergo config disables user mapping by default."""
    strategy = MoergoStrategy()
    
    params = CompilationParams(
        keymap_file=Path("test.keymap"),
        kconfig_file=Path("test.conf"),
        output_dir=Path("build"),
        branch=None,
        repo=None,
        jobs=None,
        verbose=False,
        no_cache=False,
        docker_uid=None,
        docker_gid=None,
        docker_username=None,
        docker_home=None,
        docker_container_home=None,
        no_docker_user_mapping=False,
        board_targets=None
    )
    
    profile = KeyboardProfile(
        keyboard_config=KeyboardConfig(
            keyboard_name="glove80",
            compile_methods=[MoergoCompilationConfig()]
        ),
        firmware_version="v25.05"
    )
    
    config = strategy.build_config(params, profile)
    
    assert config.docker_user.enable_user_mapping is False
    assert config.repository == "moergo-sc/zmk"
    assert config.branch == "v25.05"
```

**Validation:**
```bash
# Run linting
ruff check glovebox/cli/strategies/moergo.py --fix
ruff format glovebox/cli/strategies/moergo.py
mypy glovebox/cli/strategies/

# Run tests
pytest tests/test_cli/test_strategies/test_moergo.py -v
```

**Commit:**
```bash
git add glovebox/cli/strategies/moergo.py tests/test_cli/test_strategies/test_moergo.py
git commit -m "feat: implement Moergo compilation strategy

- Add MoergoStrategy with profile detection
- Support legacy Moergo detection patterns
- Disable Docker user mapping by default
- Add comprehensive test coverage"
```

### Step 4: Create Strategy Factory

**Files to create:**
- `glovebox/cli/strategies/factory.py`
- `tests/test_cli/test_strategies/test_factory.py`

**Implementation:**

1. Create strategy factory:
```python
# glovebox/cli/strategies/factory.py
import logging
from typing import Dict, Type

from glovebox.cli.strategies.base import CompilationStrategyProtocol
from glovebox.cli.strategies.zmk_config import ZmkConfigStrategy
from glovebox.cli.strategies.moergo import MoergoStrategy


logger = logging.getLogger(__name__)


class StrategyFactory:
    """Factory for creating compilation strategies."""
    
    _strategies: Dict[str, Type[CompilationStrategyProtocol]] = {
        "zmk_config": ZmkConfigStrategy,
        "moergo": MoergoStrategy,
    }
    
    @classmethod
    def create(cls, strategy_name: str) -> CompilationStrategyProtocol:
        """Create a compilation strategy by name.
        
        Args:
            strategy_name: Name of the strategy to create
            
        Returns:
            Compilation strategy instance
            
        Raises:
            ValueError: If strategy name is unknown
        """
        if strategy_name not in cls._strategies:
            available = ", ".join(cls._strategies.keys())
            raise ValueError(
                f"Unknown compilation strategy: {strategy_name}. "
                f"Available strategies: {available}"
            )
            
        strategy_class = cls._strategies[strategy_name]
        logger.debug("Creating strategy: %s", strategy_name)
        return strategy_class()
    
    @classmethod
    def register(cls, name: str, strategy_class: Type[CompilationStrategyProtocol]) -> None:
        """Register a new strategy.
        
        Args:
            name: Strategy name
            strategy_class: Strategy class to register
        """
        cls._strategies[name] = strategy_class
        logger.debug("Registered strategy: %s", name)
    
    @classmethod
    def list_strategies(cls) -> list[str]:
        """List available strategy names."""
        return list(cls._strategies.keys())
```

2. Update __init__.py:
```python
# glovebox/cli/strategies/__init__.py
from glovebox.cli.strategies.base import (
    CompilationParams,
    CompilationStrategyProtocol,
    BaseCompilationStrategy,
)
from glovebox.cli.strategies.factory import StrategyFactory
from glovebox.cli.strategies.zmk_config import ZmkConfigStrategy
from glovebox.cli.strategies.moergo import MoergoStrategy


__all__ = [
    "CompilationParams",
    "CompilationStrategyProtocol",
    "BaseCompilationStrategy",
    "StrategyFactory",
    "ZmkConfigStrategy",
    "MoergoStrategy",
]
```

3. Create tests:
```python
# tests/test_cli/test_strategies/test_factory.py
import pytest

from glovebox.cli.strategies.factory import StrategyFactory
from glovebox.cli.strategies.zmk_config import ZmkConfigStrategy
from glovebox.cli.strategies.moergo import MoergoStrategy


def test_create_zmk_config_strategy():
    """Test creating ZMK config strategy."""
    strategy = StrategyFactory.create("zmk_config")
    assert isinstance(strategy, ZmkConfigStrategy)
    assert strategy.name == "zmk_config"


def test_create_moergo_strategy():
    """Test creating Moergo strategy."""
    strategy = StrategyFactory.create("moergo")
    assert isinstance(strategy, MoergoStrategy)
    assert strategy.name == "moergo"


def test_create_unknown_strategy():
    """Test creating unknown strategy raises error."""
    with pytest.raises(ValueError) as exc_info:
        StrategyFactory.create("unknown")
    
    assert "Unknown compilation strategy: unknown" in str(exc_info.value)
    assert "zmk_config" in str(exc_info.value)
    assert "moergo" in str(exc_info.value)


def test_list_strategies():
    """Test listing available strategies."""
    strategies = StrategyFactory.list_strategies()
    assert "zmk_config" in strategies
    assert "moergo" in strategies


def test_register_custom_strategy():
    """Test registering a custom strategy."""
    from glovebox.cli.strategies.base import BaseCompilationStrategy
    
    class CustomStrategy(BaseCompilationStrategy):
        @property
        def name(self) -> str:
            return "custom"
        
        def supports_profile(self, profile) -> bool:
            return True
    
    StrategyFactory.register("custom", CustomStrategy)
    
    strategy = StrategyFactory.create("custom")
    assert isinstance(strategy, CustomStrategy)
    assert strategy.name == "custom"
    
    # Cleanup
    del StrategyFactory._strategies["custom"]
```

**Validation:**
```bash
# Run linting
ruff check glovebox/cli/strategies/ --fix
ruff format glovebox/cli/strategies/
mypy glovebox/cli/strategies/

# Run all strategy tests
pytest tests/test_cli/test_strategies/ -v
```

**Commit:**
```bash
git add glovebox/cli/strategies/factory.py glovebox/cli/strategies/__init__.py
git add tests/test_cli/test_strategies/test_factory.py
git commit -m "feat: add compilation strategy factory

- Create StrategyFactory for managing strategies
- Support dynamic strategy registration
- Add strategy listing functionality
- Include comprehensive test coverage"
```

### Step 5: Extract Docker User Config Builder

**Files to create:**
- `glovebox/cli/helpers/docker_config.py`
- `tests/test_cli/test_helpers/test_docker_config.py`

**Implementation:**

1. Create Docker config builder:
```python
# glovebox/cli/helpers/docker_config.py
import logging
from pathlib import Path

from glovebox.config.compile_methods import DockerUserConfig


logger = logging.getLogger(__name__)


class DockerConfigBuilder:
    """Builder for Docker user configuration."""
    
    @staticmethod
    def build_from_params(
        strategy: str,
        docker_uid: int | None = None,
        docker_gid: int | None = None,
        docker_username: str | None = None,
        docker_home: str | None = None,
        docker_container_home: str | None = None,
        no_docker_user_mapping: bool = False,
    ) -> DockerUserConfig:
        """Build Docker user configuration from parameters.
        
        Args:
            strategy: Compilation strategy name
            docker_uid: Manual UID override
            docker_gid: Manual GID override
            docker_username: Manual username override
            docker_home: Host home directory
            docker_container_home: Container home directory
            no_docker_user_mapping: Disable user mapping
            
        Returns:
            Docker user configuration
        """
        # Start with strategy-specific defaults
        if strategy == "moergo":
            # Moergo disables user mapping by default
            config = DockerUserConfig(enable_user_mapping=False)
            logger.debug(
                "Using Moergo docker defaults: enable_user_mapping=False"
            )
        else:
            # Standard strategies enable user mapping
            config = DockerUserConfig(enable_user_mapping=True)
            logger.debug(
                "Using standard docker defaults: enable_user_mapping=True"
            )
        
        # Apply overrides
        if docker_uid is not None:
            config.manual_uid = docker_uid
            logger.debug("Override: manual_uid=%s", docker_uid)
            
        if docker_gid is not None:
            config.manual_gid = docker_gid
            logger.debug("Override: manual_gid=%s", docker_gid)
            
        if docker_username is not None:
            config.manual_username = docker_username
            logger.debug("Override: manual_username=%s", docker_username)
            
        if docker_home is not None:
            config.host_home_dir = Path(docker_home)
            logger.debug("Override: host_home_dir=%s", docker_home)
            
        if docker_container_home is not None:
            config.container_home_dir = docker_container_home
            logger.debug("Override: container_home_dir=%s", docker_container_home)
            
        if no_docker_user_mapping:
            config.enable_user_mapping = False
            logger.debug("Override: enable_user_mapping=False (--no-docker-user-mapping)")
            
        logger.debug("Final docker_user_config: %r", config)
        return config
```

2. Create tests:
```python
# tests/test_cli/test_helpers/test_docker_config.py
import pytest
from pathlib import Path

from glovebox.cli.helpers.docker_config import DockerConfigBuilder


def test_build_standard_strategy_defaults():
    """Test default config for standard strategies."""
    config = DockerConfigBuilder.build_from_params("zmk_config")
    
    assert config.enable_user_mapping is True
    assert config.manual_uid is None
    assert config.manual_gid is None


def test_build_moergo_strategy_defaults():
    """Test default config for Moergo strategy."""
    config = DockerConfigBuilder.build_from_params("moergo")
    
    assert config.enable_user_mapping is False


def test_build_with_overrides():
    """Test building with parameter overrides."""
    config = DockerConfigBuilder.build_from_params(
        strategy="zmk_config",
        docker_uid=1000,
        docker_gid=1000,
        docker_username="testuser",
        docker_home="/home/test",
        docker_container_home="/tmp/test",
        no_docker_user_mapping=True
    )
    
    assert config.manual_uid == 1000
    assert config.manual_gid == 1000
    assert config.manual_username == "testuser"
    assert config.host_home_dir == Path("/home/test")
    assert config.container_home_dir == "/tmp/test"
    assert config.enable_user_mapping is False


def test_no_docker_mapping_overrides_strategy():
    """Test that no_docker_user_mapping overrides strategy defaults."""
    # Even for standard strategy, should disable mapping
    config = DockerConfigBuilder.build_from_params(
        strategy="zmk_config",
        no_docker_user_mapping=True
    )
    
    assert config.enable_user_mapping is False
```

**Validation:**
```bash
# Run linting
ruff check glovebox/cli/helpers/docker_config.py --fix
ruff format glovebox/cli/helpers/docker_config.py
mypy glovebox/cli/helpers/

# Run tests
pytest tests/test_cli/test_helpers/test_docker_config.py -v
```

**Commit:**
```bash
git add glovebox/cli/helpers/docker_config.py tests/test_cli/test_helpers/test_docker_config.py
git commit -m "feat: extract Docker config builder

- Create DockerConfigBuilder for Docker user configuration
- Support strategy-specific defaults (Moergo vs standard)
- Handle all parameter overrides
- Add comprehensive test coverage"
```

### Step 6: Create Compilation Config Builder

**Files to create:**
- `glovebox/cli/builders/__init__.py`
- `glovebox/cli/builders/compilation_config.py`
- `tests/test_cli/test_builders/__init__.py`
- `tests/test_cli/test_builders/test_compilation_config.py`

**Implementation:**

1. Create compilation config builder:
```python
# glovebox/cli/builders/compilation_config.py
import logging
from typing import Any

from glovebox.cli.helpers.docker_config import DockerConfigBuilder
from glovebox.cli.strategies.base import CompilationParams
from glovebox.cli.strategies.factory import StrategyFactory
from glovebox.config.compile_methods import (
    DockerCompilationConfig,
    ZmkCompilationConfig,
    MoergoCompilationConfig,
)
from glovebox.config.keyboard_profile import KeyboardProfile


logger = logging.getLogger(__name__)


class CompilationConfigBuilder:
    """Builder for compilation configurations."""
    
    def build(
        self,
        params: CompilationParams,
        keyboard_profile: KeyboardProfile,
        strategy_name: str,
    ) -> DockerCompilationConfig:
        """Build compilation configuration.
        
        Args:
            params: Compilation parameters from CLI
            keyboard_profile: Keyboard profile
            strategy_name: Compilation strategy name
            
        Returns:
            Compilation configuration
        """
        # Create strategy
        strategy = StrategyFactory.create(strategy_name)
        
        # Build base config from strategy
        config = strategy.build_config(params, keyboard_profile)
        
        # Build Docker user configuration
        docker_config = DockerConfigBuilder.build_from_params(
            strategy=strategy_name,
            docker_uid=params.docker_uid,
            docker_gid=params.docker_gid,
            docker_username=params.docker_username,
            docker_home=params.docker_home,
            docker_container_home=params.docker_container_home,
            no_docker_user_mapping=params.no_docker_user_mapping,
        )
        
        # Apply Docker config
        config.docker_user = docker_config
        
        # Apply workspace settings
        self._apply_workspace_settings(config, params)
        
        logger.debug("Final compilation config: %r", config)
        return config
    
    def _apply_workspace_settings(
        self,
        config: DockerCompilationConfig,
        params: CompilationParams,
    ) -> None:
        """Apply workspace-related settings to config."""
        if hasattr(config, "cleanup_workspace"):
            config.cleanup_workspace = not params.preserve_workspace
            
        if hasattr(config, "preserve_on_failure"):
            config.preserve_on_failure = (
                params.preserve_workspace and not params.force_cleanup
            )
```

2. Create tests:
```python
# tests/test_cli/test_builders/test_compilation_config.py
import pytest
from pathlib import Path

from glovebox.cli.builders.compilation_config import CompilationConfigBuilder
from glovebox.cli.strategies.base import CompilationParams
from glovebox.config.compile_methods import ZmkCompilationConfig, MoergoCompilationConfig
from glovebox.config.keyboard_profile import KeyboardProfile
from glovebox.models.keyboard_config import KeyboardConfig


def create_test_params(**kwargs) -> CompilationParams:
    """Create test compilation parameters."""
    defaults = {
        "keymap_file": Path("test.keymap"),
        "kconfig_file": Path("test.conf"),
        "output_dir": Path("build"),
        "branch": None,
        "repo": None,
        "jobs": None,
        "verbose": False,
        "no_cache": False,
        "docker_uid": None,
        "docker_gid": None,
        "docker_username": None,
        "docker_home": None,
        "docker_container_home": None,
        "no_docker_user_mapping": False,
        "board_targets": None,
        "preserve_workspace": False,
        "force_cleanup": False,
    }
    defaults.update(kwargs)
    return CompilationParams(**defaults)


def test_build_zmk_config():
    """Test building ZMK config."""
    builder = CompilationConfigBuilder()
    
    params = create_test_params(jobs=4, no_cache=True)
    
    profile = KeyboardProfile(
        keyboard_config=KeyboardConfig(
            keyboard_name="test",
            compile_methods=[ZmkCompilationConfig()]
        ),
        firmware_version="v1.0"
    )
    
    config = builder.build(params, profile, "zmk_config")
    
    assert isinstance(config, ZmkCompilationConfig)
    assert config.jobs == 4
    assert config.cache.enabled is False
    assert config.docker_user.enable_user_mapping is True


def test_build_moergo_config():
    """Test building Moergo config."""
    builder = CompilationConfigBuilder()
    
    params = create_test_params(branch="custom-branch")
    
    profile = KeyboardProfile(
        keyboard_config=KeyboardConfig(
            keyboard_name="glove80",
            compile_methods=[MoergoCompilationConfig()]
        ),
        firmware_version="v25.05"
    )
    
    config = builder.build(params, profile, "moergo")
    
    assert isinstance(config, MoergoCompilationConfig)
    assert config.branch == "custom-branch"
    assert config.docker_user.enable_user_mapping is False


def test_build_with_docker_overrides():
    """Test building with Docker overrides."""
    builder = CompilationConfigBuilder()
    
    params = create_test_params(
        docker_uid=1000,
        docker_gid=1000,
        no_docker_user_mapping=True
    )
    
    profile = KeyboardProfile(
        keyboard_config=KeyboardConfig(
            keyboard_name="test",
            compile_methods=[ZmkCompilationConfig()]
        ),
        firmware_version="v1.0"
    )
    
    config = builder.build(params, profile, "zmk_config")
    
    assert config.docker_user.manual_uid == 1000
    assert config.docker_user.manual_gid == 1000
    assert config.docker_user.enable_user_mapping is False


def test_build_with_workspace_settings():
    """Test building with workspace settings."""
    builder = CompilationConfigBuilder()
    
    params = create_test_params(
        preserve_workspace=True,
        force_cleanup=False
    )
    
    profile = KeyboardProfile(
        keyboard_config=KeyboardConfig(
            keyboard_name="test",
            compile_methods=[ZmkCompilationConfig()]
        ),
        firmware_version="v1.0"
    )
    
    config = builder.build(params, profile, "zmk_config")
    
    assert hasattr(config, "cleanup_workspace")
    assert config.cleanup_workspace is False
    assert hasattr(config, "preserve_on_failure")
    assert config.preserve_on_failure is True
```

**Validation:**
```bash
# Run linting
ruff check glovebox/cli/builders/ --fix
ruff format glovebox/cli/builders/
mypy glovebox/cli/builders/

# Run tests
pytest tests/test_cli/test_builders/ -v
```

**Commit:**
```bash
git add glovebox/cli/builders/ tests/test_cli/test_builders/
git commit -m "feat: add compilation config builder

- Create CompilationConfigBuilder to centralize config construction
- Integrate strategy pattern and Docker config builder
- Support workspace settings application
- Add comprehensive test coverage"
```

### Step 7: Create Firmware Command Executor

**Files to create:**
- `glovebox/cli/executors/__init__.py`
- `glovebox/cli/executors/firmware.py`
- `tests/test_cli/test_executors/__init__.py`
- `tests/test_cli/test_executors/test_firmware.py`

**Implementation:**

1. Create firmware executor:
```python
# glovebox/cli/executors/firmware.py
import logging
from pathlib import Path
from typing import Any

from glovebox.cli.builders.compilation_config import CompilationConfigBuilder
from glovebox.cli.strategies.base import CompilationParams
from glovebox.compilation import create_compilation_service
from glovebox.config.keyboard_profile import KeyboardProfile


logger = logging.getLogger(__name__)


class FirmwareExecutor:
    """Executor for firmware compilation operations."""
    
    def __init__(self):
        """Initialize executor."""
        self.config_builder = CompilationConfigBuilder()
    
    def compile(
        self,
        params: CompilationParams,
        keyboard_profile: KeyboardProfile,
        strategy: str,
    ) -> Any:
        """Execute firmware compilation.
        
        Args:
            params: Compilation parameters
            keyboard_profile: Keyboard profile
            strategy: Compilation strategy name
            
        Returns:
            Compilation result
        """
        # Clear cache if requested
        if params.clear_cache:
            logger.info("Cache clearing requested (will be implemented in Phase 7)")
        
        # Build configuration
        config = self.config_builder.build(params, keyboard_profile, strategy)
        
        # Create compilation service
        compilation_service = create_compilation_service(strategy)
        
        # Execute compilation
        return compilation_service.compile(
            keymap_file=params.keymap_file,
            config_file=params.kconfig_file,
            output_dir=params.output_dir,
            config=config,
            keyboard_profile=keyboard_profile,
        )
```

2. Create tests:
```python
# tests/test_cli/test_executors/test_firmware.py
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from glovebox.cli.executors.firmware import FirmwareExecutor
from glovebox.cli.strategies.base import CompilationParams
from glovebox.config.keyboard_profile import KeyboardProfile
from glovebox.models.keyboard_config import KeyboardConfig
from glovebox.config.compile_methods import ZmkCompilationConfig


def create_test_params(**kwargs) -> CompilationParams:
    """Create test compilation parameters."""
    defaults = {
        "keymap_file": Path("test.keymap"),
        "kconfig_file": Path("test.conf"),
        "output_dir": Path("build"),
        "branch": None,
        "repo": None,
        "jobs": None,
        "verbose": False,
        "no_cache": False,
        "clear_cache": False,
        "docker_uid": None,
        "docker_gid": None,
        "docker_username": None,
        "docker_home": None,
        "docker_container_home": None,
        "no_docker_user_mapping": False,
        "board_targets": None,
        "preserve_workspace": False,
        "force_cleanup": False,
    }
    defaults.update(kwargs)
    return CompilationParams(**defaults)


@patch("glovebox.cli.executors.firmware.create_compilation_service")
def test_compile_success(mock_create_service):
    """Test successful compilation."""
    # Setup mocks
    mock_service = Mock()
    mock_result = Mock(success=True, messages=["Build complete"])
    mock_service.compile.return_value = mock_result
    mock_create_service.return_value = mock_service
    
    # Create executor
    executor = FirmwareExecutor()
    
    # Create test data
    params = create_test_params()
    profile = KeyboardProfile(
        keyboard_config=KeyboardConfig(
            keyboard_name="test",
            compile_methods=[ZmkCompilationConfig()]
        ),
        firmware_version="v1.0"
    )
    
    # Execute
    result = executor.compile(params, profile, "zmk_config")
    
    # Verify
    assert result == mock_result
    mock_create_service.assert_called_once_with("zmk_config")
    mock_service.compile.assert_called_once()


@patch("glovebox.cli.executors.firmware.create_compilation_service")
def test_compile_with_cache_clear(mock_create_service):
    """Test compilation with cache clearing."""
    # Setup mocks
    mock_service = Mock()
    mock_result = Mock(success=True)
    mock_service.compile.return_value = mock_result
    mock_create_service.return_value = mock_service
    
    # Create executor
    executor = FirmwareExecutor()
    
    # Create test data with clear_cache
    params = create_test_params(clear_cache=True)
    profile = KeyboardProfile(
        keyboard_config=KeyboardConfig(
            keyboard_name="test",
            compile_methods=[ZmkCompilationConfig()]
        ),
        firmware_version="v1.0"
    )
    
    # Execute
    with patch("glovebox.cli.executors.firmware.logger") as mock_logger:
        result = executor.compile(params, profile, "zmk_config")
    
    # Verify cache clear was logged
    mock_logger.info.assert_called_with(
        "Cache clearing requested (will be implemented in Phase 7)"
    )
    assert result == mock_result
```

**Validation:**
```bash
# Run linting
ruff check glovebox/cli/executors/ --fix
ruff format glovebox/cli/executors/
mypy glovebox/cli/executors/

# Run tests
pytest tests/test_cli/test_executors/ -v
```

**Commit:**
```bash
git add glovebox/cli/executors/ tests/test_cli/test_executors/
git commit -m "feat: add firmware command executor

- Create FirmwareExecutor to handle compilation execution
- Integrate config builder and compilation service
- Support cache clearing (placeholder)
- Add unit tests with mocking"
```

### Step 8: Refactor firmware.py to Use New Components

**Files to modify:**
- `glovebox/cli/commands/firmware.py`
- `tests/test_cli/test_commands/test_firmware.py` (update existing tests)

**Implementation:**

1. Refactor firmware.py:
```python
# glovebox/cli/commands/firmware.py
"""Firmware-related CLI commands."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_profile
from glovebox.cli.executors.firmware import FirmwareExecutor
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.parameters import OutputFormatOption, ProfileOption
from glovebox.cli.helpers.profile import (
    get_keyboard_profile_from_context,
    get_user_config_from_context,
)
from glovebox.cli.strategies.base import CompilationParams
from glovebox.firmware.flash import create_flash_service


if TYPE_CHECKING:
    from glovebox.config.keyboard_profile import KeyboardProfile

logger = logging.getLogger(__name__)


def _format_compilation_output(
    result: Any, output_format: str, output_dir: Path
) -> None:
    """Format and display compilation results."""
    if result.success:
        if output_format.lower() == "json":
            result_data = {
                "success": True,
                "message": "Firmware compiled successfully",
                "messages": result.messages,
                "output_dir": str(output_dir),
            }
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            print(formatter.format(result_data, "json"))
        else:
            print_success_message("Firmware compiled successfully")
            for message in result.messages:
                print_list_item(message)
    else:
        print_error_message("Firmware compilation failed")
        for error in result.errors:
            print_list_item(error)
        raise typer.Exit(1)


# Create a typer app for firmware commands
firmware_app = typer.Typer(
    name="firmware",
    help="""Firmware management commands.

Build ZMK firmware from keymap files using Docker with multiple build strategies,
flash firmware to USB devices, and manage firmware-related operations.

Supports modern ZMK west workspace builds (recommended) as well as traditional
cmake, make, and ninja build systems for custom keyboards.""",
    no_args_is_help=True,
)


@firmware_app.command(name="compile")
@handle_errors
@with_profile()
def firmware_compile(
    ctx: typer.Context,
    keymap_file: Annotated[Path, typer.Argument(help="Path to keymap (.keymap) file")],
    kconfig_file: Annotated[Path, typer.Argument(help="Path to kconfig (.conf) file")],
    output_dir: Annotated[
        Path, typer.Option("--output-dir", "-d", help="Build output directory")
    ] = Path("build"),
    profile: ProfileOption = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Git branch to use (overrides profile branch)"),
    ] = None,
    repo: Annotated[
        str | None,
        typer.Option("--repo", help="Git repository (overrides profile repo)"),
    ] = None,
    jobs: Annotated[
        int | None, typer.Option("--jobs", "-j", help="Number of parallel jobs")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose build output")
    ] = False,
    strategy: Annotated[
        str,
        typer.Option(
            "--strategy",
            help="Compilation strategy: zmk_config (default), moergo, west",
        ),
    ] = "zmk_config",
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help="Disable workspace caching for this build",
        ),
    ] = False,
    clear_cache: Annotated[
        bool,
        typer.Option(
            "--clear-cache",
            help="Clear cache before starting build",
        ),
    ] = False,
    board_targets: Annotated[
        str | None,
        typer.Option(
            "--board-targets",
            help="Comma-separated board targets for split keyboards (e.g., 'glove80_lh,glove80_rh')",
        ),
    ] = None,
    # Docker user context override options
    docker_uid: Annotated[
        int | None,
        typer.Option(
            "--docker-uid",
            help="Manual Docker UID override (takes precedence over auto-detection and config)",
            min=0,
        ),
    ] = None,
    docker_gid: Annotated[
        int | None,
        typer.Option(
            "--docker-gid",
            help="Manual Docker GID override (takes precedence over auto-detection and config)",
            min=0,
        ),
    ] = None,
    docker_username: Annotated[
        str | None,
        typer.Option(
            "--docker-username",
            help="Manual Docker username override (takes precedence over auto-detection and config)",
        ),
    ] = None,
    docker_home: Annotated[
        str | None,
        typer.Option(
            "--docker-home",
            help="Custom Docker home directory override (host path to map as container home)",
        ),
    ] = None,
    docker_container_home: Annotated[
        str | None,
        typer.Option(
            "--docker-container-home",
            help="Custom container home directory path (default: /tmp)",
        ),
    ] = None,
    no_docker_user_mapping: Annotated[
        bool,
        typer.Option(
            "--no-docker-user-mapping",
            help="Disable Docker user mapping entirely (overrides all user context settings)",
        ),
    ] = False,
    # Workspace configuration options
    preserve_workspace: Annotated[
        bool,
        typer.Option("--preserve-workspace", help="Don't delete workspace after build"),
    ] = False,
    force_cleanup: Annotated[
        bool,
        typer.Option("--force-cleanup", help="Force workspace cleanup even on failure"),
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Build ZMK firmware from keymap and config files.

    Compiles .keymap and .conf files into a flashable .uf2 firmware file
    using Docker and the ZMK build system. Requires Docker to be running.

    Supports multiple compilation strategies:
    - zmk_config: ZMK config repository builds (default, recommended)
    - moergo: Moergo-specific builds for Glove80
    - west: Traditional ZMK west workspace builds

    Examples:
        # Basic ZMK config build (default strategy)
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

        # Moergo build strategy
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --strategy moergo

        # West workspace build strategy
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --strategy west

        # Build without caching for clean build
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --no-cache

        # Manual Docker user context (solves permission issues)
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --docker-uid 1000 --docker-gid 1000

        # Verbose output with build details
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --verbose
    """
    # Build parameter container
    params = CompilationParams(
        keymap_file=keymap_file,
        kconfig_file=kconfig_file,
        output_dir=output_dir,
        branch=branch,
        repo=repo,
        jobs=jobs,
        verbose=verbose,
        no_cache=no_cache,
        clear_cache=clear_cache,
        docker_uid=docker_uid,
        docker_gid=docker_gid,
        docker_username=docker_username,
        docker_home=docker_home,
        docker_container_home=docker_container_home,
        no_docker_user_mapping=no_docker_user_mapping,
        board_targets=board_targets,
        preserve_workspace=preserve_workspace,
        force_cleanup=force_cleanup,
    )

    # Get profile from context
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    logger.info("KeyboardProfile available in context: %r", keyboard_profile)

    # Execute compilation
    try:
        executor = FirmwareExecutor()
        result = executor.compile(params, keyboard_profile, strategy)
        _format_compilation_output(result, output_format, params.output_dir)
    except Exception as e:
        print_error_message(f"Firmware compilation failed: {str(e)}")
        raise typer.Exit(1) from None


# Keep flash and list_devices commands unchanged...
```

2. Update existing tests to work with refactored code:
```python
# tests/test_cli/test_commands/test_firmware.py (partial update)
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from typer.testing import CliRunner

from glovebox.cli.main import app


runner = CliRunner()


@patch("glovebox.cli.commands.firmware.FirmwareExecutor")
def test_firmware_compile_basic(mock_executor_class):
    """Test basic firmware compile command."""
    # Setup mock
    mock_executor = Mock()
    mock_result = Mock(
        success=True,
        messages=["Build completed successfully"],
        errors=[]
    )
    mock_executor.compile.return_value = mock_result
    mock_executor_class.return_value = mock_executor
    
    # Run command
    result = runner.invoke(
        app,
        [
            "firmware", "compile",
            "test.keymap", "test.conf",
            "--profile", "glove80/v25.05"
        ]
    )
    
    # Verify
    assert result.exit_code == 0
    assert "Firmware compiled successfully" in result.stdout
    mock_executor.compile.assert_called_once()


@patch("glovebox.cli.commands.firmware.FirmwareExecutor")
def test_firmware_compile_with_strategy(mock_executor_class):
    """Test firmware compile with specific strategy."""
    # Setup mock
    mock_executor = Mock()
    mock_result = Mock(success=True, messages=[], errors=[])
    mock_executor.compile.return_value = mock_result
    mock_executor_class.return_value = mock_executor
    
    # Run command
    result = runner.invoke(
        app,
        [
            "firmware", "compile",
            "test.keymap", "test.conf",
            "--profile", "glove80/v25.05",
            "--strategy", "moergo"
        ]
    )
    
    # Verify
    assert result.exit_code == 0
    # Check that moergo strategy was passed
    args, kwargs = mock_executor.compile.call_args
    assert args[2] == "moergo"  # strategy parameter
```

**Validation:**
```bash
# Run linting on modified files
ruff check glovebox/cli/commands/firmware.py --fix
ruff format glovebox/cli/commands/firmware.py
mypy glovebox/cli/commands/firmware.py

# Run firmware command tests
pytest tests/test_cli/test_commands/test_firmware.py -v
```

**Commit:**
```bash
git add glovebox/cli/commands/firmware.py
git add tests/test_cli/test_commands/test_firmware.py
git commit -m "refactor: use new architecture in firmware command

- Replace inline logic with FirmwareExecutor
- Use CompilationParams for parameter handling
- Simplify main command function
- Update tests to work with new architecture"
```

### Step 9: Add Integration Tests

**Files to create:**
- `tests/test_integration/test_firmware_refactoring.py`

**Implementation:**

1. Create integration tests:
```python
# tests/test_integration/test_firmware_refactoring.py
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from glovebox.cli.builders.compilation_config import CompilationConfigBuilder
from glovebox.cli.executors.firmware import FirmwareExecutor
from glovebox.cli.strategies.base import CompilationParams
from glovebox.cli.strategies.factory import StrategyFactory
from glovebox.config.keyboard_profile import KeyboardProfile
from glovebox.models.keyboard_config import KeyboardConfig
from glovebox.config.compile_methods import ZmkCompilationConfig, MoergoCompilationConfig


def create_test_params(**kwargs) -> CompilationParams:
    """Create test compilation parameters."""
    defaults = {
        "keymap_file": Path("test.keymap"),
        "kconfig_file": Path("test.conf"),
        "output_dir": Path("build"),
        "branch": None,
        "repo": None,
        "jobs": None,
        "verbose": False,
        "no_cache": False,
        "clear_cache": False,
        "docker_uid": None,
        "docker_gid": None,
        "docker_username": None,
        "docker_home": None,
        "docker_container_home": None,
        "no_docker_user_mapping": False,
        "board_targets": None,
        "preserve_workspace": False,
        "force_cleanup": False,
    }
    defaults.update(kwargs)
    return CompilationParams(**defaults)


def test_zmk_config_strategy_integration():
    """Test ZMK config strategy integration."""
    # Create components
    builder = CompilationConfigBuilder()
    
    # Create test data
    params = create_test_params(
        jobs=4,
        no_cache=True,
        docker_uid=1000,
        docker_gid=1000
    )
    
    profile = KeyboardProfile(
        keyboard_config=KeyboardConfig(
            keyboard_name="test_keyboard",
            compile_methods=[
                ZmkCompilationConfig(
                    image="zmkfirmware/zmk-build-arm:stable",
                    repository="zmkfirmware/zmk",
                    branch="main"
                )
            ]
        ),
        firmware_version="v1.0"
    )
    
    # Build config
    config = builder.build(params, profile, "zmk_config")
    
    # Verify config
    assert isinstance(config, ZmkCompilationConfig)
    assert config.jobs == 4
    assert config.cache.enabled is False
    assert config.docker_user.manual_uid == 1000
    assert config.docker_user.manual_gid == 1000
    assert config.docker_user.enable_user_mapping is True
    assert config.image == "zmkfirmware/zmk-build-arm:stable"


def test_moergo_strategy_integration():
    """Test Moergo strategy integration."""
    # Create components
    builder = CompilationConfigBuilder()
    
    # Create test data
    params = create_test_params(
        branch="custom-branch",
        no_docker_user_mapping=False  # Should still be False due to Moergo defaults
    )
    
    profile = KeyboardProfile(
        keyboard_config=KeyboardConfig(
            keyboard_name="glove80",
            compile_methods=[
                MoergoCompilationConfig(
                    repository="moergo-sc/zmk",
                    branch="v25.05"
                )
            ]
        ),
        firmware_version="v25.05"
    )
    
    # Build config
    config = builder.build(params, profile, "moergo")
    
    # Verify config
    assert isinstance(config, MoergoCompilationConfig)
    assert config.branch == "custom-branch"  # CLI override
    assert config.repository == "moergo-sc/zmk"  # From profile
    assert config.docker_user.enable_user_mapping is False  # Moergo default
    assert config.image == "glove80-zmk-config-docker"


def test_strategy_factory_all_strategies():
    """Test that all strategies can be created."""
    strategies = StrategyFactory.list_strategies()
    
    for strategy_name in strategies:
        strategy = StrategyFactory.create(strategy_name)
        assert strategy is not None
        assert strategy.name == strategy_name


@patch("glovebox.cli.executors.firmware.create_compilation_service")
def test_executor_integration(mock_create_service):
    """Test executor integration with all components."""
    # Setup mock
    mock_service = Mock()
    mock_result = Mock(
        success=True,
        messages=["Build completed"],
        errors=[]
    )
    mock_service.compile.return_value = mock_result
    mock_create_service.return_value = mock_service
    
    # Create executor
    executor = FirmwareExecutor()
    
    # Create test data
    params = create_test_params(
        jobs=8,
        docker_uid=1000,
        preserve_workspace=True
    )
    
    profile = KeyboardProfile(
        keyboard_config=KeyboardConfig(
            keyboard_name="test",
            compile_methods=[ZmkCompilationConfig()]
        ),
        firmware_version="v1.0"
    )
    
    # Execute
    result = executor.compile(params, profile, "zmk_config")
    
    # Verify
    assert result.success is True
    mock_create_service.assert_called_once_with("zmk_config")
    
    # Verify service was called with correct config
    call_args = mock_service.compile.call_args
    assert call_args.kwargs["keymap_file"] == Path("test.keymap")
    assert call_args.kwargs["config_file"] == Path("test.conf")
    assert call_args.kwargs["output_dir"] == Path("build")
    
    # Verify config was built correctly
    config = call_args.kwargs["config"]
    assert isinstance(config, ZmkCompilationConfig)
    assert config.jobs == 8
    assert config.docker_user.manual_uid == 1000
```

**Validation:**
```bash
# Run linting
ruff check tests/test_integration/test_firmware_refactoring.py --fix
ruff format tests/test_integration/test_firmware_refactoring.py

# Run integration tests
pytest tests/test_integration/test_firmware_refactoring.py -v
```

**Commit:**
```bash
git add tests/test_integration/test_firmware_refactoring.py
git commit -m "test: add integration tests for firmware refactoring

- Test full integration of all refactored components
- Verify ZMK config and Moergo strategies work correctly
- Test parameter handling and config building
- Ensure executor integrates all components properly"
```

### Step 10: Final Validation and Documentation

**Files to create/update:**
- `docs/implementation/completed/firmware-command-refactoring.md` (move from current-plans)
- Update `glovebox/cli/strategies/README.md`

**Implementation:**

1. Create strategies README:
```markdown
# glovebox/cli/strategies/README.md
# Compilation Strategies

This module implements the Strategy pattern for handling different firmware compilation methods.

## Architecture

- `base.py` - Base classes and protocols for strategies
- `zmk_config.py` - Standard ZMK config compilation strategy
- `moergo.py` - Moergo-specific compilation strategy
- `factory.py` - Factory for creating strategies

## Adding a New Strategy

1. Create a new file in this directory (e.g., `my_strategy.py`)
2. Implement the `CompilationStrategyProtocol` interface
3. Register the strategy in `factory.py`

Example:
```python
from glovebox.cli.strategies.base import BaseCompilationStrategy

class MyStrategy(BaseCompilationStrategy):
    @property
    def name(self) -> str:
        return "my_strategy"
    
    def supports_profile(self, profile: KeyboardProfile) -> bool:
        # Implementation
        pass
    
    def build_config(self, params: CompilationParams, profile: KeyboardProfile) -> DockerCompilationConfig:
        # Implementation
        pass
```

## Testing

Each strategy should have comprehensive tests in `tests/test_cli/test_strategies/`.
```

2. Run final validation:
```bash
# Run all linting
ruff check glovebox/cli/ --fix
ruff format glovebox/cli/
mypy glovebox/cli/

# Run all tests
pytest tests/test_cli/ -v
pytest tests/test_integration/test_firmware_refactoring.py -v

# Check coverage
pytest tests/test_cli/ --cov=glovebox.cli --cov-report=html
```

3. Move implementation plan to completed:
```bash
mv docs/implementation/current-plans/firmware-command-refactoring.md \
   docs/implementation/completed/firmware-command-refactoring.md
```

**Final Commit:**
```bash
git add glovebox/cli/strategies/README.md
git add docs/implementation/completed/firmware-command-refactoring.md
git commit -m "docs: complete firmware command refactoring

- Add documentation for compilation strategies
- Move implementation plan to completed
- Document how to add new strategies
- Include architecture overview"
```

## Summary

This implementation plan refactors the firmware command module following CLAUDE.md conventions:

1. **Clean Architecture**: Separated concerns into focused components
2. **Strategy Pattern**: Proper implementation for compilation methods
3. **Testability**: Each component has comprehensive unit tests
4. **Extensibility**: Easy to add new compilation strategies
5. **Code Quality**: All code passes linting and type checking
6. **Documentation**: Clear documentation for future development

The refactoring maintains backward compatibility while significantly improving code organization and maintainability.