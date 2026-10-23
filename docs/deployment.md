# Deploy with Dockge

This guide deploys the published GHCR image as a Dockge-managed Compose stack on
the existing Ubuntu VM. It does not provision or configure the VM or Dockge.
Image publication does **not** update the running stack: an operator chooses
when to pull and deploy an image in Dockge.

## Create the stack

1. Open the existing Dockge UI and add a stack named `fussball`.
2. Copy the repository's root [`compose.yaml`](../compose.yaml) into Dockge's
   Compose editor. Dockge saves it as the stack's `compose.yaml`.
3. Add a stack `.env` file with the image tag to deploy:

   ```dotenv
   IMAGE_TAG=latest
   ```

   `latest` selects the latest image published from `main`. For a pinned
   release, use the full commit SHA tag instead, for example
   `IMAGE_TAG=0123456789abcdef0123456789abcdef01234567`.
4. Save and deploy the stack in Dockge. The app listens on port `8000`; make it
   reachable through the existing VM/network setup as appropriate.

## Configure administrator score correction

Administrator sign-in is optional. To enable score corrections, add all three
settings to the Dockge stack `.env` file and use deployment-only values:

```dotenv
ADMIN_USERNAME=your-admin-name
ADMIN_PASSWORD=use-a-unique-long-password
ADMIN_SESSION_SECRET=generate-a-separate-random-secret
ADMIN_SESSION_COOKIE_SECURE=true
```

`ADMIN_SESSION_SECRET` signs the browser session cookie; it is separate from the
administrator password. Keep these values in Dockge or another deployment
secret store, never in the repository. `ADMIN_SESSION_COOKIE_SECURE` defaults
to `true` so browsers send the session cookie only over HTTPS. Set it to `false`
only for local development over plain HTTP.

If any of the username, password, or session-signing secret is absent, the app
omits administrator controls and disables sign-in and score mutation routes.
Match browsing and public match submission remain available.

The Compose file declares the named volume `fussball-data` with an explicit
Docker volume name, mounted at `/app/data`. The application database is
`/app/data/database.db`. Keep this volume name and do not remove the volume when
recreating the stack. Removing/recreating the container or using Dockge's
ordinary redeploy leaves the database intact; deleting the Docker volume does
not.

## Back up before every deployment

**Take and verify a fresh SQLite backup before every deployment/redeploy.**
For a first install there is no existing application database yet; before each
later deployment, complete these backup steps before pulling/redeploying.

The following commands run on the Ubuntu VM from a directory where you want to
keep backups. They use Python's SQLite backup API against the persistent volume,
so the snapshot is consistent even if the app is serving requests. The backup
file is written outside Docker's volume and remains available if that volume is
damaged.

```bash
mkdir -p backups
BACKUP_FILE="fussball-$(date -u +%Y%m%dT%H%M%SZ).db"
docker run --rm \
  --mount source=fussball-data,target=/source,readonly \
  --mount "type=bind,source=$PWD/backups,target=/backup" \
  --user 0 \
  --entrypoint python \
  -e "BACKUP_FILE=/backup/$BACKUP_FILE" \
  ghcr.io/l-schier/fussball:${IMAGE_TAG:-latest} \
  -c 'import os, sqlite3; source=sqlite3.connect("file:/source/database.db?mode=ro", uri=True); target=sqlite3.connect(os.environ["BACKUP_FILE"]); source.backup(target); target.close(); source.close()'
test -s "backups/$BACKUP_FILE"
```

The runner image tag is only used to provide Python; it does not deploy or
change the running stack. Keep backups on storage independent from the Docker
volume and retain them according to your own retention policy. A failed backup
or an empty backup file is a stop condition: do not deploy until a valid backup
has been made.

To locate/check the persistent volume on the VM:

```bash
docker volume inspect fussball-data
docker volume ls --filter name=fussball-data
```

The database file inside it is `database.db`. Do not edit, move, or copy the
live SQLite file directly while the application is running; use the SQLite
backup API shown above.

## Pull and redeploy manually

After the backup has been verified:

1. In the Dockge `fussball` stack, edit `.env` and set `IMAGE_TAG` to `latest`
   or the full commit SHA you intend to deploy.
2. Save the stack, then use Dockge's **Pull** action to fetch the selected
   image. Pulling alone does not deploy it.
3. Review the selected tag and use Dockge's **Deploy** action to recreate the
   service with that image. Do not rely on image publication to update the
   stack; there is no automatic deployment.
4. Check the stack logs and confirm the app's `/health` endpoint responds with
   HTTP 200 before considering the deployment complete.

Keep `fussball-data` unchanged when editing or recreating the stack. Do not use
`docker compose down --volumes` or otherwise delete this volume as part of an
image update.

## Migrations and deployment failures

On every container start, the image entrypoint runs
`alembic -c /app/alembic.ini upgrade head` before starting Uvicorn. The app
starts only when that command succeeds. A new image can therefore update the
schema at startup; a schema migration is a data-changing deployment, which is
why a fresh backup is mandatory each time.

When a contributor changes SQLAlchemy models/schema, they should create and
review a migration revision from the repository root:

```bash
uv run alembic revision --autogenerate -m "describe the schema change"
```

Review the generated file under `alembic/versions/`, correct it if autogenerate
missed or misrepresented a change, and test the upgrade (and downgrade when
appropriate) against a disposable database. Commit the revision with the model
change. Do not edit an already-published migration; add a new revision instead.
The container applies committed revisions automatically at startup.

If startup or migration fails, Dockge logs show the Alembic error and the
container exits instead of serving requests. Do not repeatedly restart it or
delete the data volume. Preserve the pre-deployment backup, inspect the logs,
and fix the migration/image issue. If the deployment has changed the database
and you need to return to the previous app/schema, stop the stack and restore
the pre-deployment backup first; then deploy the previous known-good commit tag.
Do not assume an older image can safely use a database already upgraded by a
newer migration.

## Restore a backup

Restoring replaces the current database. Stop the `fussball` stack in Dockge
first so the app cannot write during recovery. Set `BACKUP_FILE` below to the
name of the verified backup in `./backups`, then run:

```bash
BACKUP_FILE=fussball-20261021T120000Z.db
docker run --rm \
  --mount source=fussball-data,target=/app/data \
  --mount "type=bind,source=$PWD/backups,target=/backup,readonly" \
  --entrypoint python \
  -e "BACKUP_FILE=/backup/$BACKUP_FILE" \
  ghcr.io/l-schier/fussball:${IMAGE_TAG:-latest} \
  -c 'import os, sqlite3; source=sqlite3.connect("file:" + os.environ["BACKUP_FILE"] + "?mode=ro", uri=True); target=sqlite3.connect("/app/data/database.db"); source.backup(target); target.close(); source.close()'
```

Start the previous known-good image tag from Dockge and check the logs and
`/health`. The entrypoint will apply migrations present in that image when it
starts. Keep the failed database/stack logs until recovery is confirmed; the
backup itself is not deleted by the restore operation.
