# Automations

## `aeascripts`

The bootstrap installer. Downloaded on its own or as part of a clone, it clones
this repository into `$HOME/bin/aea-scripts` and adds that directory to `$PATH`
in the bash profile. It is not used for anything else.

## Running from CI

The Python tools are optimized for the Bitbucket Pipelines environment used by
the AEA Data Editor and also run by hand on Linux. Set `CI` (to `true`, `1`,
`yes`, or `on`) to disable animation and colour so logs stay plain; each step
still prints one line per action and outcome.

Authentication in the cloud is described in [Installation](../installation/index.md).
