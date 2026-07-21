# Sample judge inputs

All artifacts represent the same small TypeScript cart change.

- Base commit: `f150ddf846322b493128d3a8f544b3fd26d02f6f`
- Head commit: `1ca372ed2d434ab4192b70cf59413e4d14c93add`
- `sample-project.bundle`: upload in **Git bundle** mode; choose the base and head commits above.
- `sample-project-base.zip` + `sample-change.diff`: upload together in **Project + diff** mode.
- `sample-project-base.zip` + `sample-change.patch`: equivalent patch-form test.
- `source-repository/`: inspect the final source locally; its internal Git metadata is removed after artifact generation.

These files contain no secrets and the application analyzes them without executing their code.
