# Runbook

Operations for the live site. Commands assume `gcloud` is signed in to the project, and use
`$REGION` for the Cloud Run region. Where to find each secret: [README](../README.md#which-secret-goes-where).

## Quick reference

| Situation | Fastest safe action |
| --- | --- |
| A content change made answers worse | [Roll back the index](#roll-back-the-index) |
| A deploy broke the API | [Roll back the API](#roll-back-the-api-or-site) |
| Unexpected spend or abuse | [Pause chat](#pause-chat) |
| A key may have leaked | [Rotate it](#rotate-keys), then check the usage report |

## Roll back the index

Every ingest keeps the previous versions, so rolling back is one switch and needs no rebuild.

1. GitHub > Actions > **rollback-index** > Run workflow, with `list`. The output shows recent
   versions with their status (`active`, `retired`, `failed`) and git commit.
2. Run it again with the id of the `retired` version you want. It becomes `active` and the
   current one becomes `retired`, in one transaction. Answers switch on the next question.

`failed` versions cannot be activated; they failed a gate on purpose. To go forward again, run
the workflow with the newer id, or re-run the **ingest** workflow.

Locally, with the owner connection string:

```bash
export PROVENANCE_DATABASE_URL='<Neon owner URL>'
uv run --project ingest python -m ingest versions
uv run --project ingest python -m ingest activate <id>
```

## Roll back the API or site

- **API:** Cloud Run keeps earlier revisions.

  ```bash
  gcloud run revisions list --service provenance-api --region $REGION
  gcloud run services update-traffic provenance-api --region $REGION --to-revisions <revision>=100
  ```

  The next deploy sends traffic to the new revision again, so revert the bad commit on `main`
  as well.
- **Site:** Vercel dashboard > the project > Deployments > pick the last good one > Promote, or
  `vercel rollback`. Then revert the bad commit.
- **Migrations** only ever add; there are no down migrations. Fix forward with a new migration.

## Pause chat

Three levels, from gentle to total. The site, project pages and approved starter answers keep
working in every case.

1. **Soft pause (preferred).** Set the spend cap to zero so every question gets the "the guide
   is resting" message and no model is called:

   ```bash
   gcloud run services update provenance-api --region $REGION \
     --update-env-vars PROVENANCE_DAILY_SPEND_CAP_USD=0
   ```

   This creates a new revision in seconds. To make it survive the next deploy, also set the
   GitHub variable `DAILY_SPEND_CAP_USD` to `0`. Undo by setting both back (default `1.0`).
2. **Close the API.** Remove public access; the site shows its "offline" state.

   ```bash
   gcloud run services remove-iam-policy-binding provenance-api --region $REGION \
     --member allUsers --role roles/run.invoker
   ```

   Restore with `add-iam-policy-binding` and the same arguments. The next deploy also restores
   it (`--allow-unauthenticated`), so set `DEPLOY_ENABLED` to `false` while it should stay closed.
3. **Cut the model off.** Disable the key in the Anthropic console. Questions then fail with the
   generic "unavailable" message. Use this if the key itself may be misused elsewhere.

## Rotate keys

Secret Manager values are read when an instance starts, so after adding a version, roll a new
revision:

```bash
printf '%s' '<new value>' | gcloud secrets versions add <secret-name> --data-file=-
gcloud run services update provenance-api --region $REGION --update-labels rotated=$(date +%s)
```

| Secret | Where the new value comes from | Side effects |
| --- | --- | --- |
| `provenance-anthropic-api-key` | Anthropic console > API keys | Disable the old key after the new revision is serving |
| `provenance-session-secret` | `openssl rand -base64 48` | Open chats get a new session automatically |
| `provenance-ip-hash-salt` | `openssl rand -base64 24` | Rate-limit counters start again |
| `provenance-turnstile-secret` | Cloudflare > Turnstile > the widget > Rotate secret | None, if the site key is unchanged |
| `provenance-api-database-url` | Neon > Roles > `provenance_api` > Reset password | Old URL stops at once; update the secret first |

Other credentials:

- **Neon owner password:** reset in Neon, then update the GitHub secrets
  `NEON_MIGRATE_DATABASE_URL` and `NEON_INGEST_DATABASE_URL`.
- **Vercel token:** create a new one in Vercel > Account > Tokens, update `VERCEL_TOKEN`, delete
  the old one.
- **Turnstile site key:** if the widget is recreated, update `NEXT_PUBLIC_TURNSTILE_SITE_KEY` in
  Vercel and re-run the deploy workflow.
- **Google Cloud:** there is no key to rotate; GitHub signs in through Workload Identity
  Federation.

After any rotation, check the usage report for anything unexpected:

```bash
PROVENANCE_DATABASE_URL='<provenance_api role URL>' \
  uv run --project apps/api python -m provenance.report --days 7
```

## Health checks

- `GET https://<api>/health` returns `{"status": "ok"}` and wakes a cold instance.
- The deploy workflow's smoke test calls it after each deploy.
- Cloud Run > provenance-api > Logs shows warnings for failed chats; stack traces stay in logs and
  never reach visitors.
