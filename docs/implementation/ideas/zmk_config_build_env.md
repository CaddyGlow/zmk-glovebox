```py
       github_env_vars = {
           'base_dir': '${GITHUB_WORKSPACE}',  # or new_tmp_dir if zephyr/module.yml exists
           'zmk_load_arg': ' -DZMK_EXTRA_MODULES="${GITHUB_WORKSPACE}"' if True else '',  # TODO: check zephyr/module.yml
           'extra_west_args': f'-S "{snippet}"' if snippet else '',
           'extra_cmake_args': f'-DSHIELD="{shield}"' + '${zmk_load_arg}' if shield else '${zmk_load_arg}',
           'display_name': f'{shield} - {board}' if shield else board,
           'artifact_name': f'{shield}-{board}-zmk' if shield else f'{board}-zmk',
           'build_dir': 'build/${artifact_name}',
           'zephyr_version': '${ZEPHYR_VERSION}',
       }
```
