# Example: How ZmkWestService Would Use Shared Workspace Cache Utils

## Current Implementation (ZmkWestService)

```python
# In glovebox/compilation/services/zmk_west_service.py

def _generate_workspace_cache_key(
    self,
    config: ZmkCompilationConfig,
    level: str = "full",
    keymap_file: Path | None = None,
    config_file: Path | None = None,
) -> str:
    # ... 60+ lines of complex logic with build matrix handling
```

## Refactored Implementation

```python
# In glovebox/compilation/services/zmk_west_service.py

from glovebox.core.workspace_cache_utils import generate_workspace_cache_key
from glovebox.core.cache_v2.models import CacheKey

def _generate_workspace_cache_key(
    self,
    config: ZmkCompilationConfig,
    level: str = "full",
    keymap_file: Path | None = None,
    config_file: Path | None = None,
) -> str:
    """Generate cache key for workspace based on configuration and cache level."""
    
    # Prepare build matrix data for shared function
    build_matrix_data = None
    if level in ["full", "build"]:
        build_matrix_data = config.build_matrix.model_dump_json()
    
    # Prepare additional parts for build level
    additional_parts = []
    if level == "build":
        if keymap_file and keymap_file.exists():
            keymap_hash = CacheKey.from_path(keymap_file)
            additional_parts.append(keymap_hash)
        
        if config_file and config_file.exists():
            config_hash = CacheKey.from_path(config_file)
            additional_parts.append(config_hash)
    
    # Use shared utility with appropriate parameters
    return generate_workspace_cache_key(
        repository=config.repository,
        branch=config.branch,
        level=level,
        image=config.image,
        build_matrix_data=build_matrix_data,
        additional_parts=additional_parts if additional_parts else None,
    )
```

## Benefits

1. **Code Reuse**: Both CLI and ZmkWestService use the same core logic
2. **Consistency**: Cache keys are generated the same way across the system
3. **Maintainability**: Changes to cache key logic only need to be made in one place
4. **Testability**: Shared utilities can be tested independently
5. **Flexibility**: ZmkWestService gets all its advanced features while CLI gets simple interface

## Shared Constants

Both implementations now use the same TTL values from `get_workspace_cache_ttls()`:

- Base level: 30 days (repository only)
- Branch level: 1 day (repository + branch + image)  
- Full level: 12 hours (repository + branch + image + build matrix)
- Build level: 1 hour (full + input file hashes)

This ensures consistency across the entire system.