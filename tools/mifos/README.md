# A local Mifos X, for checking the CredLens export

Mifos X's back end is Apache Fineract. This folder starts one on your laptop with Docker,
so `src/db/mifos_load.py` can load CredLens's synthetic merchants and loans into it and
check what Mifos X makes of them. For local testing only; never on the hosted server.

Needs Docker Desktop running, and about 1.5 GB of free memory for Docker (stop other
containers first). The first start takes about two minutes while Fineract builds its
database.

```
copy tools\mifos\.env.example tools\mifos\.env      (then put your own two passwords in it)
docker compose -f tools/mifos/docker-compose.yml --env-file tools/mifos/.env up -d
python -m src.db.mifos_adapter          (writes the export, from data/app.db)
python -m src.db.mifos_load --merchants 50
docker compose -f tools/mifos/docker-compose.yml down        (stop; add -v to delete its data)
```

Ready when https://localhost:8443/fineract-provider/actuator/health shows
`{"status":"UP"}`. The API login is Fineract's demo login (user `mifos`, password
`password`, tenant `default`); the port is open to this laptop only.

`.env` holds the local database passwords and is never committed. `01-init.sh` is
Apache Fineract's own database set-up script (Apache License 2.0).

Result of Oct 14, 2026 (image `apache/fineract:724b0d742c`): 50 merchants and their 85
loans loaded with no request refused; 73 repayments posted; for all 85 loans Mifos X's
own status (closed or still running) matched CredLens. It took 17 minutes on the lead's
laptop (about 12 seconds per loan, most of it Fineract's own work).
