# Sentinel Agent Guidelines

## Project Mission

This is the primary software repository for a RoboMaster autonomous sentry robot. The main development areas are ROS 2 Jazzy, NVIDIA Isaac Sim 6.0.1, a four-module swerve chassis, gimbal control, navigation, perception, adversarial simulation, and later Isaac Lab / reinforcement learning.

The repository combines ROS 2 packages (`ros2_ws/src`), Python training code (`training`), Isaac Sim integration (`isaac_sim`), system configuration (`config`), and a shared C11 protocol (`firmware/protocol`). Treat `firmware/vendor/`, third-party imports, and generated `ros2_ws/{build,install,log}` content as out of scope unless a task explicitly targets them.

## Runtime Paths and Host Boundaries

Do not assume one absolute path works on every developer machine.

### Current remote 4090 simulation host (2026-10-02)

- Simulation work root: `/home/ubuntu/RoboMaster`
- Isaac Lab runtime: `/home/ubuntu/RoboMaster/IsaacLab`
- Original field (never overwrite): `/home/ubuntu/RMwork/sentryusd/Sentry_space/RMUL2026.usd`
- Physics baseline: `/home/ubuntu/RMwork/sentryusd/Sentry_space/RMUL2026_sentry_work.usd`
- Robot source assets: `/home/ubuntu/RMwork/sentryusd/Sentry/Sentry/`
- Debug scenes: `/home/ubuntu/RoboMaster/scenes/`
- Runtime results: `/home/ubuntu/RoboMaster/results/`

The remote `/home/ubuntu/RoboMaster` directory is a simulation work root, not automatically the canonical Git checkout. Verify the actual `sentry-ros` clone before any Git operation. Do not run `git init` merely because a directory has an empty or unexpected `.git`.

### Repository checkout

Each developer may clone this repository elsewhere. Resolve paths relative to the repository root whenever possible. Do not hard-code the historical `/home/xkddyl/...` workstation paths into new code.

### Official/upstream runtime

Treat the installed Isaac Sim / Isaac Lab runtime as upstream. Do not modify its source, site-packages, or official examples to implement project behavior. Put adapters and project logic under this repository's `isaac_sim/`, `training/`, `tools/`, `ros2_ws/src/sentinel_*`, or equivalent team-owned modules.

See `docs/development/REMOTE_4090_SIM_GUIDE.md` and
`docs/development/TEAM_COLLABORATION_GUIDE.md` before editing simulation or cross-team interfaces.

## Integration and Asset Rules

- Never copy the canonical USD into the ROS 2 workspace. ROS-side code must resolve the single source through `SENTRY_USD_PATH` or an explicit launch/config parameter.
- Never overwrite an approved stage. Any new Stage 5D/V3 USD must be derived into a new file.
- The approved USD path is never inferred from this repository; pass it explicitly through
  `SENTRY_USD_PATH` after human GUI approval. Historical Stage5C/Stage5D files are evidence only.
- Do not guess Isaac Sim APIs from memory. Inspect the installed Isaac Sim 6.0.1 extensions and standalone examples first, then reuse the local API demonstrated there.
- Keep simulation, HIL, and real-hardware boundaries explicit. Validation must progress Mock → simulation → HIL → real hardware.
- Do not create duplicate ROS packages. `sentinel_interfaces` owns the current custom messages/services; assess the existing `isaac_sim` and `sentinel_bringup` integration before proposing another bridge package.

## Required Workflow

Before editing, read `README.md`, `ARCHITECTURE.md`, and the relevant module documentation, especially `docs/TOPIC_CONTRACT.md` or `docs/REAL_INTEGRATION.md`. Run `git status --short` first, preserve all user changes, and modify only files required by the task. Never overwrite, revert, reformat, or otherwise absorb unrelated work.

After completing a task, report files changed, commands run and their results, checks not performed, remaining risks or hardware-dependent validation, `git diff --stat`, and `git status --short`. Update `PROJECT_STATE.md` after each completed integration phase.

All validation gates must be truthful. A failed test must return and print FAIL. Shell exit status/output and JSON reports must agree; never print PASS when the report gate failed.

## Build and Verification

Use repository-provided commands from the workspace root. Integration entry points live in `tools/integration/`.

- `bash tools/ubuntu/run_checks.sh`: ROS-independent unit tests and Python byte-compilation.
- `python3 -m unittest discover -s tests -v`: focused ROS-independent tests.
- `tools/integration/build_ros2.sh`: build `ros2_ws` only after dependencies are available and authorized.
- `bash tools/ubuntu/run_smoke.sh`: Mock control-loop smoke test after building.
- `bash tools/ubuntu/run_sim.sh`: ROS simulation stack after Mock succeeds.

For ROS 2 changes, build affected packages, run relevant tests, and verify names, types, ownership, and safety flow against `docs/TOPIC_CONTRACT.md`. For communication-protocol changes, check Python encoding/decoding, ROS 2 messages/bridge behavior, and the STM32 implementation together.

## Safety and Permission Boundaries

- Do not run `sudo`, `apt install`, `pip install`, or `tools/ubuntu/bootstrap_jazzy.sh` automatically. State what is missing and why, then obtain authorization.
- Do not modify system ROS 2 or any file in the official Isaac Sim installation.
- Do not alter Git history, create remotes, or discard user changes. Commits/pushes are
  allowed only when the user explicitly requests repository integration.
- Never independently run `run_real.sh`, `release_estop.sh`, OpenOCD, `st-flash`, `dfu-util`, or any firmware flashing operation.
- Do not connect to, command, or drive a real chassis, gimbal, or launcher without explicit item-by-item confirmation. Safety supervision and emergency stop must never be bypassed.
