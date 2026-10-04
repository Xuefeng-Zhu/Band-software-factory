# Docker capacity preflight

For future readiness, configure explicit daemon resource minima under `runtime.docker_resources`. Both keys are required positive integers; absent, misspelled or malformed values block validation/readiness. No existing run configuration or freeze is migrated automatically.

```yaml
runtime:
  docker_resources:
    min_cpus: 2
    min_memory_mib: 3072
```

The example allows one 2 GiB service plus 1 GiB of total memory headroom for the daemon, harness and supporting processes. This is an operator-selected minimum, not a universal workload budget. A nominal 4 GiB VM can report slightly less than 4096 MiB after system reservations; compare the daemon's actual `MemTotal`, not the VM settings label. Increase the minima for simultaneous services, browser/build processes and additional stages. Two reported CPUs meet this example's CPU floor; they do not reserve CPU time or guarantee performance.

Doctor's `docker_daemon` check now requires a successful structured `docker info` response containing a server version, positive integer `NCPU` and positive integer `MemTotal`, with both resources at or above the configured floors. Missing Docker, connection failures, timeouts, missing fields and insufficient resources fail closed. The report retains the selected endpoint, requirements, observed resources and bounded command evidence. It emits only these necessary fields, not the daemon's full proxy/configuration data.

An explicit `runtime.docker_host` is validated against the named permission profile's exact Unix socket. Every capacity query uses that host and clears inherited `DOCKER_CONTEXT`; it cannot fall back to another daemon. Without an explicit host, the Docker CLI's normal context/environment selection applies. Configure an exact host when the seat runtime uses one. These behaviors follow Docker's [info reference](https://docs.docker.com/reference/cli/docker/system/info/) and [CLI endpoint configuration](https://docs.docker.com/reference/cli/docker/).

An otherwise-ready runtime launch and dispatch preparation repeat the same read-only query because Docker capacity may have changed since doctor/freeze. Already-blocked launches do not contact Docker. Cumulative deadline checks run again after the bounded query. The probe does not resize/restart the VM, change a Docker context, create a container, or alter budgets. A failure requires an operator-reviewed environment correction and fresh evidence before a later launch; it does not authorize infrastructure intervention during an active judged run.

This checks total daemon capacity, not free memory or other workloads' consumption. Passing does not prove all concurrent services fit, establish application acceptance, replace real seat permission/build/browser evidence, or authorize a new run.
