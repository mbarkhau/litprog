
## The LitProg Command

Here we generate the `src/litprog/cli.py` file, which has the main entry point for the `litprog` cli command, which is available after running `pip install litprog`.

The module declares/does:

 - `Backtrace` library initialization
 - Logging configuration/initialization
 - The `litprog` cli command using `click`
 - Configuration of the subcommands `build`
 - File system scanning


```yaml
filepath: "src/litprog/cli.py"
inputs  : [
    "license_header_boilerplate",
    "generated_preamble",
    "common.imports",
    "module_logger",
    "cli.code",
]
```

In most cases (when installing with `pip install litprog`) this is strictly speaking not top level script. Instead there is a (platform dependent) file generated from the [`entry_points`][setup_py_entry_points] declared in `setup.py`.


### Backtrace for Nicer Stack Traces

The [`backtrace`](https://github.com/nir0s/backtrace) package produces human friendly tracebacks, but is not a requirement to use litprog. To enable it for just one invocation use `ENABLE_BACKTRACE=1 litprog --help`.

```python
# lpid = cli.code
# To enable pretty tracebacks:
#   echo "export ENABLE_BACKTRACE=1;" >> ~/.bashrc
if os.environ.get('ENABLE_BACKTRACE') == '1':
    import backtrace

    backtrace.hook(
        align=True,
        strip_path=True,
        enable_on_envvar_only=True,
    )
```

Note that the `backtrace` library messes with stdout and stderr, so it might not work together nicely with terminal based debuggers. If that's not an issue, you can enable it permanently using `echo "export ENABLE_BACKTRACE=1;" >> ~/.bashrc`.


### Logging Configuration

We use the standard python logging module throughout the codebase. Logging is
initialized using this helper function. The verbosity is set using the `--verbose` flag and controls the logging format and the level.

```python
# lpid = cli.code

class LogConfig(typ.NamedTuple):
    fmt: str
    lvl: int


def _parse_logging_config(verbosity: int) -> LogConfig:
    if verbosity == 0:
        return LogConfig(
            "%(levelname)-7s - %(message)s",
            logging.WARNING,
        )

    log_format = (
        "%(asctime)s.%(msecs)03d %(levelname)-7s "
        + "%(name)-15s - %(message)s"
    )
    if verbosity == 1:
        return LogConfig(log_format, logging.INFO)

    assert verbosity >= 2
    return LogConfig(log_format, logging.DEBUG)
```

Since the `--verbose` flag can be set both via the command group (the `cli` function) and via a sub-command, we need to deal with multiple invocations of `_configure_logging`. There are probably nicer ways of doing this if you want to get into the intricacies of the click library. The choice here is to override any previously configured logging only if the previous verbosity was lower.

```python
# lpid = cli.code

def _configure_logging(verbosity: int = 0) -> None:
    _prev_verbosity: int = getattr(_configure_logging, '_prev_verbosity', -1)

    if verbosity <= _prev_verbosity:
        return

    _configure_logging._prev_verbosity = verbosity

    # remove previous logging handlers
    for handler in list(logging.root.handlers):
        logging.root.removeHandler(handler)

    log_cfg = _parse_logging_config(verbosity)
    logging.basicConfig(
        level=log_cfg.lvl,
        format=log_cfg.fmt,
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
```


### Imperative Shell: CLI command `litprog`

Since we're declaring the entry point here, we import most of the other modules directly (and all of them indirectly). While other modules are written in a functional style and have unit tests, this module represents the [imperative shell](https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell) and thus only has a basic integration test. 

```python
# lpid = cli.code
import click

import litprog.parse
import litprog.build
import litprog.session
```

We'll be using the venerable [click][ref_click_lib] library to implement our CLI. `click` complains about use of `from __future__ import unicode_literals` [for some reason that I haven't dug into yet][ref_click_py3]. In the course of compiling LitProg to universal python using `lib3to6` the import is added. 

As far as I can tell, everything is behaving as expected, at least using ascii filenames, so the following is used to supress the warning.

```python
# lpid = cli.code
click.disable_unicode_literals_warning = True
```

We could implement `litprog` as one command atm. but in anticipation of future subcommands we'll use the `click.group` approach to implement git style cli with subcommands.

```python
# lpid = cli.code

verbosity_option = click.option(
    '-v',
    '--verbose',
    count=True,
    help="Control log level. -vv for debug level.",
)


@click.group()
@click.version_option(version="v201901.0001-alpha")
@verbosity_option
def cli(verbose: int = 0) -> None:
    """litprog cli."""
    _configure_logging(verbose)
```

### CLI sub-command `litprog build`

The `litprog build` subcommand recursively scans the `input_paths` argument for markdown files, parses them (creating a context object) and then uses the context to build the various outputs (source files, html and pdf). 

```python
# lpid = cli.code
@cli.command()
@click.argument(
    'input_paths', nargs=-1, type=click.Path(exists=True)
)
@verbosity_option
def build(
    input_paths: InputPaths,
    verbose: int = 0,
) -> None:
    _configure_logging(verbose)
    md_filepaths = sorted(_iter_markdown_filepaths(input_paths))
    context = litprog.parse.parse_context(md_filepaths)
    try:
        sys.exit(litprog.build.build(context))
    except litprog.session.SessionException:
        sys.exit(1)
```

These are the supported file extensions. It may may be worth revisiting this (for example by introducing a dedicated `.litmd` file extension), but for now I expect projects to have a dedicated directory with markdown files and this approach captures the broadest set of files.

```python
# lpid = cli.code

MARKDOWN_FILE_EXTENSIONS = {
    "markdown",
    "mdown",
    "mkdn",
    "md",
    "mkd",
    "mdwn",
    "mdtxt",
    "mdtext",
    "text",
    "Rmd",
}
```

This helper function scans the file system based on arguments to a subcommand. Note that paths that are passed directly as arguments are always selected, regardless of extension, but files that are in sub-directories are only selected if they have one of the [known extensions for markdown files](https://superuser.com/questions/249436/file-extension-for-markdown-files).

```python
# lpid = cli.code
def _iter_markdown_filepaths(
    input_paths: InputPaths
) -> FilePaths:
    for path_str in input_paths:
        path = pl.Path(path_str)
        if path.is_file():
            yield path
        else:
            for ext in MARKDOWN_FILE_EXTENSIONS:
                for fpath in path.glob(f"**/*.{ext}"):
                    yield fpath
```


### Basic Integration Test

This is a good starting point for tests. Just as a sanity check, let's see if we can import and access the `log` logger.

```yaml
lpid    : test_cli
lptype  : session
command : /usr/bin/env python
requires: [
    'src/litprog/types.py',
    'src/litprog/parse.py',
    'src/litprog/build.py',
    'src/litprog/session.py',
    'src/litprog/cli.py',
]
```

```python
# lpid = test_cli
import os
import sys
print("cwd   :", os.getcwd())
print("python:", sys.executable)
import litprog.cli as cli
print("logger:", cli.log.name)
assert cli.log.name == 'litprog.cli'
```


### The `__main__` Module

In order to also be able to run when invoked with `python -m litprog`, we need to define a `__main__.py` file.

```yaml
filepath     : "src/litprog/__main__.py"
is_executable: true
inputs       : [
    "shebang_python",
    "license_header_boilerplate",
    "generated_preamble",
    "__main__.code",
]
```

The shebang line is mostly symbolic and indicates, (in case it wasn't obvious) that `src/litprog/__main__.py` is a top level script. 

```python
# lpid = shebang_python
#!/usr/bin/env python
```

```python
# lpid = __main__.code
import litprog.cli

if __name__ == '__main__':
    litprog.cli.cli()
```

[ref_click_lib]: https://click.palletsprojects.com

[ref_click_py3]: https://click.palletsprojects.com/en/5.x/python3/