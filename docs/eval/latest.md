# Evaluation: does AgentOps find the right root cause?

Generated 2026-11-17 12:17 by `python scripts/evaluate.py`. Engines: rules.

## Accuracy

| Group | rules |
|---|---|
| other-fixtures | 6/8 (75%) |
| shoplite-fixtures | 7/7 (100%) |
| live | 5/5 (100%) |
| live-held-out | 1/1 (100%) |
| all | 19/21 (90%) |

## Is the confidence meaningful?

Brier score is the mean squared gap between confidence and being right (0 is perfect, 0.25 is a coin flip), over incidents that have a real cause. A useful confidence is high when right and low when wrong.

| Engine | Mean conf. when right | Mean conf. when wrong | Brier | False alarms on healthy |
|---|---|---|---|---|
| rules | 0.77 | 0.78 | 0.1 | 0/2 |

Accuracy by confidence band (incidents with a real cause):

| Engine | 0.00-0.50 | 0.50-0.75 | 0.75-0.90 | 0.90-1.00 |
|---|---|---|---|---|
| rules | - | 100% (n=2) | 82% (n=11) | 100% (n=6) |

## Cost

| Engine | Mean seconds per run | LLM calls | LLM tokens | Unusable LLM answers |
|---|---|---|---|---|
| rules | 0.12 | 0 | 0 | 0 |

## Every run

| Engine | Group | Scenario | Expected | Got | Conf. | Agents | Flagged | s |
|---|---|---|---|---|---|---|---|---|
| rules | live | `live:bad_config` | configuration_error | configuration_error | 0.79 | observability, config, kubernetes | 0 | 0.1 |
| rules | live | `live:db_down` | dependency_issue | dependency_issue | 0.93 | observability, dependency | 0 | 0.1 |
| rules | live | `live:latency` | traffic_incident | traffic_incident | 0.82 | observability, kubernetes | 0 | 0.1 |
| rules | live | `live:none` | unknown | unknown | 0.3 | observability, cicd | 0 | 0.1 |
| rules | live | `live:oom` | kubernetes_oom | kubernetes_oom | 0.91 | observability, kubernetes | 0 | 0.1 |
| rules | live-held-out | `live:crash` | application_error | application_error | 0.8 | observability, cicd | 0 | 0.1 |
| rules | other-fixtures | `incident-001` | deployment_induced_failure | **kubernetes_oom** | 0.77 | cicd, observability | 0 | 0.2 |
| rules | other-fixtures | `incident-002` | kubernetes_oom | kubernetes_oom | 0.62 | kubernetes, traffic, cicd | 1 | 0.2 |
| rules | other-fixtures | `incident-003` | dependency_issue | dependency_issue | 0.75 | cicd, dependency | 0 | 0.1 |
| rules | other-fixtures | `incident-004` | deployment_induced_failure | **configuration_error** | 0.79 | cicd, kubernetes, observability, config | 0 | 0.2 |
| rules | other-fixtures | `incident-005` | dependency_issue | dependency_issue | 0.88 | cicd, dependency, config, kubernetes, observability | 0 | 0.2 |
| rules | other-fixtures | `incident-006` | kubernetes_oom | kubernetes_oom | 0.52 | kubernetes, observability, cicd, config, dependency | 2 | 0.2 |
| rules | other-fixtures | `incident-007` | configuration_error | configuration_error | 0.77 | cicd, config | 0 | 0.1 |
| rules | other-fixtures | `incident-008` | dependency_issue | dependency_issue | 0.78 | cache, dependency, observability | 0 | 0.1 |
| rules | shoplite-fixtures | `shoplite-S1` | deployment_induced_failure | deployment_induced_failure | 0.81 | cicd, kubernetes, config | 0 | 0.1 |
| rules | shoplite-fixtures | `shoplite-S2` | kubernetes_oom | kubernetes_oom | 0.93 | kubernetes, cicd | 0 | 0.1 |
| rules | shoplite-fixtures | `shoplite-S3` | traffic_incident | traffic_incident | 0.88 | observability, kubernetes | 0 | 0.1 |
| rules | shoplite-fixtures | `shoplite-S4` | configuration_error | configuration_error | 0.9 | cicd, kubernetes | 0 | 0.1 |
| rules | shoplite-fixtures | `shoplite-S5` | dependency_issue | dependency_issue | 0.93 | cicd, dependency, observability | 0 | 0.1 |
| rules | shoplite-fixtures | `shoplite-S6` | multi_layer_failure | multi_layer_failure | 0.99 | kubernetes, cicd, observability | 0 | 0.1 |
| rules | shoplite-fixtures | `shoplite-S7` | unknown | unknown | 0.3 | cicd, observability | 0 | 0.1 |
