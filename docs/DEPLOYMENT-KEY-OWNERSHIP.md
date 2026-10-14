# Zippy Logistics — Deployment Key Ownership Matrix

> Document which credentials are used by whom, stored where, and rotation requirements.

## Credential Matrix

| Credential | Used By | Stored Where | Browser Safe? | Rotation Required? |
|------------|---------|--------------|---------------|-------------------|
| Supabase anon key | Frontend (portal/console) | Vercel env | Yes | Yes |
| Supabase service role | API workers, portal webhooks | VPS secret | No | Yes |
| Supabase JWT secret | Server-side auth verification | VPS secret | No | Yes |
| Razorpay key ID | Payment service | VPS secret | No | Yes |
| Razorpay key secret | Payment service | VPS secret | No | Yes |
| Razorpay webhook secret | Webhook verification | Vercel/VPS | No | Yes |
| Odoo API key | Hermes/Odoo adapter | VPS secret | No | Yes |
| Odoo DB password | Odoo container only | Docker secret | No | Yes |
| Paperclip API key | Governance client | VPS secret | No | Yes |
| Paperclip encryption secret | Governance encryption | VPS secret | No | Yes |
| Hermes API key | Internal services | VPS secret | No | Yes |
| Composio API key | Hermes/tool layer | VPS secret | No | Yes |
| Langfuse public key | Observability | VPS env | Possibly | No |
| Langfuse secret key | Observability | VPS secret | No | Yes |
| Honcho API key | Memory adapter | VPS secret | No | Yes |
| OpenRouter key | AI runtime | VPS secret | No | Yes |
| DeepSeek key | AI runtime | VPS secret | No | Yes |
| Mapbox token | Maps (server) | VPS secret | No | Yes |
| Mapbox public token | Maps (client) | Vercel env | Yes | Yes |
| SMTP password | Email delivery | VPS secret | No | Yes |
| SMS API key | SMS delivery | VPS secret | No | Yes |
| WhatsApp API token | WhatsApp delivery | VPS secret | No | Yes |
| Database URL | All server services | VPS secret | No | On credential rotation |
| Redis URL | Workers, API | VPS secret | No | On credential rotation |

## Storage Locations

| Location | Purpose | Access |
|----------|---------|--------|
| Vercel Environment Variables | Frontend env, public-safe values | CI/CD + Frontend build |
| VPS `/etc/zippy/.env` | Production secrets | Docker services only |
| Docker Secrets | Sensitive container config | Container-internal only |
| GitHub Actions Secrets | CI/CD deployment tokens | Workflow runners only |

## Rotation Schedule

| Credential | Frequency | Method |
|------------|-----------|--------|
| Supabase service role | Quarterly | Supabase dashboard |
| Razorpay keys | Quarterly | Razorpay dashboard |
| Odoo API key | Quarterly | Odoo user preferences |
| Paperclip API key | On compromise | Paperclip admin |
| Hermes API key | On compromise | Hermes admin |
| Langfuse keys | Annually | Langfuse dashboard |
| Database password | On compromise | Postgres admin |

## Security Rules

1. **Never commit secrets to Git** — `.env` is in `.gitignore`
2. **Never expose service-role keys to browser** — Only `NEXT_PUBLIC_*` and `VITE_*` are public-safe
3. **Never use default passwords in production** — Must fail rather than silently use weak defaults
4. **Never log secrets** — Use `api/redaction.py` for log sanitization
5. **Never share credentials across systems** — Each system has isolated credentials
6. **Rotate on compromise** — Immediately rotate + audit affected sessions
7. **Use dedicated integration accounts** — Never use admin master passwords
