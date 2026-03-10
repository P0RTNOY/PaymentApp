# Operations Runbooks

## 1. Credentials Expired (Payment Provider)
- **Symptom:** Sync tasks repeatedly fail with 401/403 errors. `Cloud Monitoring` alerts trigger for "Sync Failures > Threshold".
- **Action:** 
  1. Access the Admin Web console.
  2. Navigate to Tenant Settings > "Provider Connections".
  3. Locate the failing integration and click "Re-authenticate" to input fresh API keys.
  4. Once validated, manually click "Trigger Sync" from the Admin Console to catch up.

## 2. Webhook Signature Failures 
- **Symptom:** Incoming payloads log "Invalid Signature" repeatedly.
- **Action:**
  1. Verify the configured Webhook Secret in Secret Manager matches the external Provider.
  2. Test updating the Secret in GCP. 
  3. The API dynamically loads the secret on boot, so force a restart of the Cloud Run instances: `gcloud run services update api-service --update-env-vars FORCE_RESTART=1`.

## 3. High 5XX API Spikes
- **Symptom:** Cloud Monitoring Alert for "High 5XX Error Rate".
- **Action:**
  1. Check GCP Logs Explorer for `severity>=ERROR AND resource.type="cloud_run_revision"`.
  2. If the issue is a new deployment, roll back immediately: `gcloud run services update api-service --revision=[PREVIOUS_REVISION]`.
  3. If it is Database contention, evaluate Firestore metrics for "hot partitions".

## 4. Document Issuance Backlog
- **Symptom:** Transactions show as "Completed" but receipts are permanently "Pending".
- **Action:**
  1. Check Cloud Tasks queue `document-issuance`. If it is paused or rate-limited due to upstream APIs, increase the backoff limit.
  2. If the upstream provider (e.g. Green Invoice) is down, no action is needed until they recover. The idempotent worker will automatically succeed when retried.

## 5. Login Abuse / Credential Stuffing
- **Symptom:** Massive spikes in `/v1/auth/login` returning 401s. SlowAPI Rate limit drops (429 Too Many Requests) will trigger.
- **Action:**
  1. Monitor Cloud Armor / WAF if equipped. IP blocks will happen natively by the FastAPI limiter.
  2. For sustained botnets, block the offending CIDR blocks at the load balancer level.
