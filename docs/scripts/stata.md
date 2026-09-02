# `stataNN` / `stataNNsh`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/stata17)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Maybe Windows](https://img.shields.io/badge/-Windows-orange)

Run Stata from a Docker image. `NN` is the Stata version (`16`, `17`, `18`,
`19`). Requires a local Stata license and Docker.

```
stata17 nameofdofile.do
```

The working directory is set to that of the do file, which may not suit every
project.

`stataNNsh` opens a shell inside the same image instead of running Stata. An
Apptainer variant (`stata17-apptainer`) is available for HPC environments.
