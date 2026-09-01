# Scripts to facilitate the Data Editors and report writer's lives

These scripts streamline a few recurring steps in the AEA Data Editor workflow.
They may not work in all environments.

**Full documentation:** <https://aeadataeditor.github.io/editor-scripts/>

## Requirements

`Bash` (git bash should be fine on Windows)

![Tested on Linux](https://img.shields.io/badge/Tested-on%20Linux-success) ![Tested on macOS](https://img.shields.io/badge/Tested-on%20macOS-success) ![Partially Tested on Windows](https://img.shields.io/badge/Partially%20Tested-on%20Windows-yellow)

Some scripts have additional dependencies (`pandoc`, `wkhtmltopdf` or `docker`,
`qpdf`); each script's documentation page lists its own requirements and platform
support.

## Installation

The repository contains a script which should handle installation. As with anything that downloads scripts that run on your computer, you should exercise caution.

### Method 1

Use this method if you have no other scripts in `$HOME/bin`. That directory is usually part of the command search path in bash and Git-bash.

1. Check if there are scripts in `$HOME/bin`: `ls $HOME/bin`
   - If the above gives you an error, there is no `bin` directory, and you can safely use this method.
   - If the above does not give an error, but shows no files, you can also (probably) use this method.
2. If the directory `$HOME/bin` exists, this will delete it (but will safely fail if there are files there): `rmdir $HOME/bin`
3. Now you are ready to clone into `$HOME/bin`:

```bash
cd $HOME
rmdir bin
git clone https://github.com/AEADataEditor/editor-scripts.git bin
```

### Method 2

1. Clone the repository into your usual Workspace, and open a Terminal in that directory.
2. Run `./aeascripts`

### Method 3 (convenient, less secure)

```bash
bash <(wget -qO - https://raw.githubusercontent.com/AEADataEditor/editor-scripts/main/aeascripts)
```

### Python scripts

The Python scripts in this repository can be installed as command-line tools using `pip` or `uv`. This makes them available in your `PATH` on all platforms, including Windows.

```bash
pip install git+https://github.com/AEADataEditor/editor-scripts.git
```

Or using the included helper script (add `--uv` to use `uv` instead of `pip`).
The helper script always installs with `--upgrade`, so running it is both install and update:

```bash
./install.sh        # uses pip
./install.sh --uv   # uses uv
```

To uninstall:

```bash
pip uninstall aea-editor-scripts
```

## Updating

```bash
cd $HOME/bin/
[[ -d aea-scripts ]] && cd aea-scripts
git pull
```

## Documentation

Per-script reference, cloud setup, and maintenance scripts are documented at
<https://aeadataeditor.github.io/editor-scripts/>, built from [`docs/`](docs/)
with [MyST](https://mystmd.org/).
