# Render setup for David

The map stays on GitHub Pages. Accounts and posts live on a free Render web service in **ohio**, using the Postgres database that already exists:

| | |
| --- | --- |
| Database name | `shareschooling-db` |
| Region | ohio |
| Postgres | 18 |
| Database | `shareschooling_db` |
| User | `shareschooling_db_user` |

`render.yaml` does **not** create a database. It creates only the free web service and sets `DATABASE_URL` from that database's **internal** connection string (`connectionString`). Do not add a second database, a paid web service, Redis, or a disk.

Confirm on Render's pricing page that the database you already created is still the plan you approved (about $6 a month) before you sync the blueprint. This repo does not create or pay for anything.

## 1. Create the web service

After this pull request is merged (or from this branch, if you want to try it first):

1. In the Render dashboard, New → Blueprint, and point it at this repo. Render reads `render.yaml`.
2. Confirm the web service region is **ohio**, the plan is **free**, and the only database reference is the existing `shareschooling-db`. If the blueprint screen offers to create a new database, cancel and create the web service by hand instead (step 3).
3. Hand path, if you prefer it: New → Web Service, this repo, region **ohio**, plan **Free**.
   - Build: `pip install -r api/requirements.txt`
   - Start: `gunicorn --workers 1 --bind 0.0.0.0:$PORT api.wsgi:app`
   - Health check path: `/api/health`

## 2. Environment variables

Set these on the web service. Do not put them in git.

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Internal connection string of `shareschooling-db`. The blueprint fills this from `connectionString`. If you create the service by hand, copy the **internal** URL from the database page. The service must stay in ohio to use it. |
| `TOKEN_SECRET` | A long random string. The blueprint can generate one. |
| `ADMIN_EMAIL` | Your email. The first admin is created from this. There is no public "become admin" button. |
| `ADMIN_PASSWORD` | At least 8 characters. |
| `ADMIN_DISPLAY_NAME` | `David` (optional) |
| `CORS_ORIGINS` | `https://dparkerson7.github.io` |

Leave Stripe keys unset. Payments in this build are "Mark as paid (test)" and the admin grant. No card is charged.

The first deploy runs the SQL in `api/migrations/` and creates the admin account when `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set. A later deploy does not reset that password. To reset it once, open the service shell and run:

```shell
ADMIN_RESET=yes python -m api.reset_admin
```

with `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DATABASE_URL`, and `TOKEN_SECRET` already in the environment.

## 3. Point the test site at the API

1. Copy the service's public `https://` URL (it ends in `.onrender.com`).
2. Set `communityApi` in `data/site.json` to that URL with no trailing path.
3. Friends-test defaults are already in `modules`: `reviews` true, every other module false. Leave them that way for the friends test. The preview you see before this step shows every module on purpose.
4. Run `python3 tools/build_site.py` and deploy the GitHub Pages site.
5. Open the test site. The first request after a quiet period can take about a minute while the free service wakes. The page should say it is waking the server.

Until `communityApi` is set, the Pages site keeps working and shows a labeled community preview with sample families. The map does not depend on Render.
