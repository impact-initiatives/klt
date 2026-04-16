# klt (Kobotoolobx Load Tool)

[![Run KLT Audit Log Pipeline (Dev)](https://github.com/impact-initiatives/klt/actions/workflows/run-audit-log.yml/badge.svg)](https://github.com/impact-initiatives/klt/actions/workflows/run-audit-log.yml)
[![Run KLT Pipeline (Dev)](https://github.com/impact-initiatives/klt/actions/workflows/run-pipeline-dev.yml/badge.svg)](https://github.com/impact-initiatives/klt/actions/workflows/run-pipeline-dev.yml)
[![Run dbt in ACI](https://github.com/impact-initiatives/matryoshka/actions/workflows/run-dbt-aci.yml/badge.svg)](https://github.com/impact-initiatives/matryoshka/actions/workflows/run-dbt-aci.yml)

## Launche the pipeline
```{python}
uv run klt
```

## Secrets

Inside `.dlt/secrets.toml` file, add the following content:
```
kobo_server="https://kobo.host.org"
kobo_token="token"
```
