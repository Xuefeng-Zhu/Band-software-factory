# Docker capacity preflight

For future readiness, configure explicit daemon resource minima under `runtime.docker_resources`. Both keys are required positive integers; absent, misspelled or malformed values block validation/readiness. No existing run configuration or freeze is migrated automatically.

```yaml
runtime:
  docker_resources:
    min_cpus: 2
    min_memory_mib: 3072
```

The example budgets one 2 GiB service plus 1 GiB of total memory headroom for the daemon, harness and supporting processes; it does not reserve that memory. This is an operator-selected minimum, not a universal workload budget. A nominal 4 GiB VM can report slightly less than 4096 MiB after system reservations; compare the daemon's actual `MemTotal`, not the VM settings label. A larger intended workload needs its own capacity assessment, within the user's approved resource limits. Two reported CPUs meet this example's CPU floor; they do not reserve CPU time or guarantee performance.

## Constrained example with a 2,048 MiB global VM cap

Keep the user's global VM ceiling at **2,048 MiB**. The [recorded capped environment](../evidence/run5-user-2g-cap-20261004/orbstack-user-2g-cap.json) reported `MemTotal: 2073866240` bytes, or 1,977.793 MiB. For a future separately authorized configuration using this constrained environment, an explicit total-capacity floor can be:

```yaml
runtime:
  docker_resources:
    min_cpus: 2
    min_memory_mib: 1977
```

This rounds the observed total down to the schema's integer MiB unit. It is not an empirically proven minimum workload requirement, free-RAM measurement, guaranteed 2 GiB service allocation, or reserved headroom. The [post-run supplied Stage 1 suite](../evidence/run5-postrun-isolated-20261004/README.md) passed 120 checks under that cap, but independent review still rejected the candidate; this does not establish concurrent-service fit, later-stage readiness or application acceptance. Run 5 is closed, and this example neither changes its configuration nor authorizes a restart.

The 3,072 MiB headroom example above intentionally remains unchanged and fails on this capped environment. Even a 2,048 MiB *effective-memory minimum* fails because the VM's reported total is lower than its configured ceiling. The 1,977 MiB floor still rejects a 1 GiB daemon. Select the appropriate explicit floor and refresh evidence for a future scope; do not resize Docker or reduce the floor automatically to obtain PASS. Retain the exact approved Docker endpoint and its matching permission-profile socket.

This guard enforces minima only. A larger VM also passes the same floor, so the guard cannot verify the user's maximum cap; preserve a separate read-only observation of the configured ceiling. No maximum-memory schema key is supported. The default example is not silently replaced by the constrained example.

## Check behavior and admission

Doctor's `docker_daemon` check now requires a successful structured `docker info` response containing a server version, positive integer `NCPU` and positive integer `MemTotal`, with both resources at or above the configured floors. Missing Docker, connection failures, timeouts, missing fields and insufficient resources fail closed. The report retains the selected endpoint, requirements, observed resources and bounded command evidence. It emits only these necessary fields, not the daemon's full proxy/configuration data.

An explicit `runtime.docker_host` is validated against the named permission profile's exact Unix socket. Every capacity query uses that host and clears inherited `DOCKER_CONTEXT`; it cannot fall back to another daemon. Without an explicit host, the Docker CLI's normal context/environment selection applies. Configure an exact host when the seat runtime uses one. These behaviors follow Docker's [info reference](https://docs.docker.com/reference/cli/docker/system/info/) and [CLI endpoint configuration](https://docs.docker.com/reference/cli/docker/).

An otherwise-ready runtime launch and dispatch preparation repeat the same read-only query because Docker capacity may have changed since doctor/freeze. Already-blocked launches do not contact Docker. Cumulative deadline checks run again after the bounded query. The probe does not resize/restart the VM, change a Docker context, create a container, or alter budgets. A failure requires an operator-reviewed environment correction and fresh evidence before a later launch; it does not authorize infrastructure intervention during an active judged run.

This checks total daemon capacity, not free memory or other workloads' consumption. Passing does not prove all concurrent services fit, establish application acceptance, replace real seat permission/build/browser evidence, or authorize a new run.
