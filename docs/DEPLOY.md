# Putting CredLens online: from a new server to a working site

Written for the person who deploys (Zamila). Owner role: D (full-stack, Humayra), Phase 12.
Every command is in the order you run it. Nothing here needs a server expert: copy a command, run it,
compare what you see with "You should see".

What the finished site is: the dashboard and the API on one address, `https://your-name/`, asking for a
user name and a password, on one small Ubuntu server. The data is the synthetic demo data. Decision
support only.

## 0. Before you start

You need:

| What | Notes |
|---|---|
| A VPS with **Ubuntu 22.04** | Choose 22.04, not 24.04: it has Python 3.10, the version we developed and tested on. **At least 2 GB of memory, 4 GB is safer**: the API needs about 1.3 GB for the first 30 to 60 seconds, then about 250 to 450 MB. 10 GB of disk (the data is about 0.6 GB). |
| A name for the site | A domain you own with an A record pointing to the server's IP address, or the host name your provider gives the server. HTTPS (step 13) needs a name, not a bare IP address. |
| Your laptop | The one that trained the model the model cards describe (the lead's), with Node.js, Python 3.10 and `pip`. |
| The code on GitHub, on `main` | The `deploy/` folder and this guide must be merged into `main` first. |

**Never run `python tasks.py train` after the model cards were written.** `train` makes a new model
version every time, and the cards, the test-month results and the audit describe one version (see
`docs/SERVER_FILES.md`). The server never trains: it gets the laptop's model file in step 7.

How the pieces fit:

    browser --https--> Nginx (password, the dashboard files, /api) --> API on 127.0.0.1:8000 --> SQLite file

## Part A: on your laptop (about 10 minutes)

### 1. Get the latest code and check it

```
git switch main
git pull
python tasks.py test
```

You should see: `... passed, ... skipped` and no `failed`.

### 2. Build the dashboard

```
cd web
npm ci
npm run build
cd ..
```

You should see: `built in ...` and a folder `web/dist` with `index.html` inside.

### 3. Pack the dashboard and the model

```
python deploy/make_bundle.py
```

You should see: `Wrote ...credlens-upload.tar.gz (about 1 MB ...)`.
If it says `NOT PACKED`, read the sentence: it names what is missing (the dashboard is not built, the
model is not trained here, or the model card was written for another model version).

### 4. (Optional but recommended) Try the real Nginx file on your laptop

Needs Docker Desktop running and the API running (`python tasks.py api`, then
`python deploy/wait_for_api.py`):

```
python deploy/test_nginx_local.py
```

You should see: a list of `[OK  ]` lines and `All checks passed.`

## Part B: on the server (about 45 minutes)

### 5. Buy the server and connect to it

**HUMAN STEP.** In the provider's panel (Hostinger: hPanel, VPS): create a VPS with Ubuntu 22.04, set a
root password (or add your SSH key), and write down the server's IP address. Then, in PowerShell on your
laptop:

```
ssh root@SERVER_IP
```

Type `yes` the first time, then the password. You should see a prompt like `root@srv123:~#`. Every
command below is typed there, as `root`. A command that starts with `sudo -u credlens` runs as the
service's own user, on purpose.

### 6. Update the server and install what CredLens needs

```
apt update && apt upgrade -y
apt install -y nginx python3 python3-venv python3-pip git libgomp1 curl apache2-utils ufw
```

If a pink screen asks about restarting services, press Enter. If the server was upgraded a lot, run
`reboot`, wait a minute, and `ssh` in again.

Open only the doors that are needed (SSH, and web):

```
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
ufw status
```

You should see `Status: active` and rules for OpenSSH and Nginx Full. (If your provider has its own
firewall in the panel, open ports 22, 80 and 443 there too.)

If the server has only 2 GB of memory, add swap so the first start does not run out of memory:

```
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
free -h
```

### 7. Get the code, set up Python, make the data

```
adduser --system --group --no-create-home --home /opt/credlens credlens
git clone https://github.com/Zamila18/CredLens.git /opt/credlens
chown -R credlens:credlens /opt/credlens
chmod 755 /opt/credlens
cd /opt/credlens
```

If the repository is private, GitHub asks for a user name and a **personal access token** instead of a
password (GitHub, Settings, Developer settings, Personal access tokens, read-only access to this one
repository). Never paste a token into a chat or a file in the repository.

Install the Python packages (about 5 minutes; it makes `/opt/credlens/.venv`):

```
sudo -u credlens python3 tasks.py setup
```

You should see pip installing packages and no red `ERROR`.

Make the synthetic data and the database (about 2 minutes; it makes about 0.6 GB):

```
sudo -u credlens python3 tasks.py data
chmod 750 /opt/credlens/data
rm -f /opt/credlens/data/raw/synthetic_bd/strength_0.5/_latent_truth.csv
```

You should see the table of row counts (`merchants 20,000`, `purchases ...`) and `users 4`. The last
command deletes the generator's hidden-truth file, which must not stay on a server.

### 8. Copy the model and the dashboard from your laptop

On your **laptop** (PowerShell, in the project folder):

```
scp credlens-upload.tar.gz root@SERVER_IP:/tmp/
```

On the **server**:

```
tar -xzf /tmp/credlens-upload.tar.gz -C /opt/credlens
chown -R credlens:credlens /opt/credlens
rm /tmp/credlens-upload.tar.gz
ls /opt/credlens/web/dist /opt/credlens/src/model/artifacts/synthetic_bd
```

You should see `index.html`, `assets` and `favicon.svg`, and `metadata.json` and `model.joblib`.

### 9. The settings file

```
cd /opt/credlens
cp deploy/env.template .env
chown credlens:credlens .env
chmod 600 .env
```

The template needs no change for the demo (production mode, synthetic data, SQLite). Only you and the
service can read it.

### 10. Check the files, then start the API as a service

```
sudo -u credlens .venv/bin/python -m src.api.preflight --server
```

You should see only `[OK  ]` lines and `Ready: the API can be started.` If a line says `FAIL`, it names the
fix; do that and run it again. (The most likely one: the model card does not match the model. Then the
bundle came from a laptop that did not train the model the cards describe.)

```
cp deploy/credlens-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now credlens-api
```

This command waits about a minute: the API builds its scorer before it can answer. Then:

```
systemctl status credlens-api --no-pager
python3 deploy/wait_for_api.py
curl -s http://127.0.0.1:8000/health
```

You should see `Active: active (running)`, `READY after ... s. Model version: synthetic_bd-...`, and
`{"status":"ok","data_mode":"synthetic_bd","banner":"Synthetic demo data. Decision support only."}`.
If it does not become ready: `journalctl -u credlens-api -n 80 --no-pager` shows why.

### 11. The password for the whole site

```
htpasswd -c /etc/nginx/credlens.htpasswd demo
chown root:www-data /etc/nginx/credlens.htpasswd
chmod 640 /etc/nginx/credlens.htpasswd
```

It asks for the password twice. Choose a long one and give it only to the people who need it, by a
private message. User name: `demo`. (More people: `htpasswd /etc/nginx/credlens.htpasswd another-name`.
Remove one: `htpasswd -D /etc/nginx/credlens.htpasswd demo`.)

### 12. Nginx

Replace `YOUR.DOMAIN` with the site's name (no `https://`):

```
cp /opt/credlens/deploy/nginx/credlens.conf /etc/nginx/sites-available/credlens
sed -i 's/server_name _;/server_name YOUR.DOMAIN;/' /etc/nginx/sites-available/credlens
ln -s /etc/nginx/sites-available/credlens /etc/nginx/sites-enabled/credlens
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

You should see `syntax is ok` and `test is successful`. Open `http://YOUR.DOMAIN/` in a browser: it asks
for the user name and password, then shows the review queue. (At this point the page is not encrypted:
do step 13 before sharing the address.)

### 13. HTTPS

The name must already point to the server (a check from your laptop: `nslookup YOUR.DOMAIN` shows the
server's IP). Then:

```
snap install --classic certbot
ln -s /snap/bin/certbot /usr/bin/certbot
certbot --nginx -d YOUR.DOMAIN -m YOUR@EMAIL --agree-tos --no-eff-email --redirect
```

You should see `Congratulations! You have successfully enabled HTTPS`. Certbot changes
`/etc/nginx/sites-available/credlens` (adds the certificate and a redirect from http to https) and renews the
certificate by itself. Check the renewal: `certbot renew --dry-run`.

If certbot fails: the name does not point to this server yet (wait, then try again), or port 80 is closed
(the provider's firewall).

**No domain?** Use a self-signed certificate: the traffic is encrypted, but every visitor's browser shows a
warning that they must accept once.

```
openssl req -x509 -nodes -days 30 -newkey rsa:2048 -subj "/CN=credlens" \
  -keyout /etc/ssl/private/credlens.key -out /etc/ssl/certs/credlens.crt
sed -i 's|listen 80;|listen 443 ssl;\n    ssl_certificate /etc/ssl/certs/credlens.crt;\n    ssl_certificate_key /etc/ssl/private/credlens.key;|' /etc/nginx/sites-available/credlens
sed -i '/listen \[::\]:80;/d' /etc/nginx/sites-available/credlens
nginx -t && systemctl reload nginx
```

then use `https://SERVER_IP/`.

### 14. Look at the finished site

From your laptop, in a browser, open `https://YOUR.DOMAIN/` and check:

- [ ] It asks for the user name and password, and refuses a wrong one.
- [ ] The banner at the top says `Synthetic demo data. Decision support only.`
- [ ] The review queue shows about 4,177 pending merchants (611 "Needs more info", 200 "Consent missing").
- [ ] Open a merchant: score, coverage and band are together; reasons in English and in Bangla (the
      switch in the sidebar).
- [ ] Record a decision as `Officer 1` (override needs a written reason); it appears in the Decision log.
- [ ] As `Admin`: the audit log shows what you just did.
- [ ] Model card page: all five data sources have a tab.
- [ ] Reload the page on `/merchants/M000031`: it still opens (it is a one-page app).
- [ ] From the laptop: `curl -I https://YOUR.DOMAIN/api/health` answers `401` (the password), and
      `https://YOUR.DOMAIN/api/docs` is not a page.

## Part C: every day

### Start, stop, look

| What | Command (on the server) |
|---|---|
| Is the API running? | `systemctl status credlens-api --no-pager` |
| Wait until it can score | `python3 /opt/credlens/deploy/wait_for_api.py` |
| Restart the API (takes about a minute) | `systemctl restart credlens-api` |
| Stop it | `systemctl stop credlens-api` |
| The API's log | `journalctl -u credlens-api -n 100 --no-pager` |
| Nginx's errors | `tail -n 50 /var/log/nginx/error.log` |
| Check every file the API needs | `sudo -u credlens /opt/credlens/.venv/bin/python -m src.api.preflight --server` |
| Disk and memory | `df -h /` and `free -h` |

After a reboot the API starts by itself (give it a minute). While it starts, visitors see a page that says
"CredLens is starting" and reloads by itself.

### Back up the decisions

Decisions and the audit log live only in the SQLite file. Before and after a demo:

```
cd /opt/credlens && sudo -u credlens python3 tasks.py backup
ls -la /opt/credlens/data/backups
```

Copy a backup to your laptop: `scp root@SERVER_IP:/opt/credlens/data/backups/app_*.db .`

### Update the site

```
cd /opt/credlens
sudo -u credlens git pull
systemctl restart credlens-api
```

If `requirements.txt` changed, also: `sudo -u credlens .venv/bin/pip install -r requirements.txt`.
For a new dashboard, make a new bundle on the laptop (steps 2 and 3), copy it (step 8) and unpack it.
**Do not** run `python tasks.py data --reset-db` on a server that holds decisions you want to keep: it
removes every decision and every audit entry. Back up first.

### Change or remove the password

`htpasswd /etc/nginx/credlens.htpasswd demo` asks for a new password for `demo`. No restart is needed.

## Part D: when something is wrong

| What you see | What it means, and what to do |
|---|---|
| "CredLens is starting" page for more than 3 minutes | The API did not start. `journalctl -u credlens-api -n 80 --no-pager`. Run the preflight check (step 10). If memory is the problem (`Killed` in the log): add swap (step 6) or a bigger server. |
| The site works but the dashboard shows red "scorer not ready" or "database not ready" messages | The API runs but a file is missing. Run the preflight check; it names the fix. |
| The browser asks for the password again and again | The user name or the password is wrong, or `/etc/nginx/credlens.htpasswd` is not readable by Nginx (step 11, the `chown` and `chmod`). |
| `502 Bad Gateway` (not the "starting" page) | Nginx's `credlens.conf` is not the file in use. `nginx -T | grep error_page` should show `/starting.html`. |
| `nginx -t` fails | It prints the line number. The most likely cause is a typo in `server_name`. |
| Certbot fails | The name does not point to this server yet, or port 80 is closed in the provider's firewall. |
| The model card page shows a warning that the card describes another model version | The model files on the server are not the ones the cards were written for. Make a new bundle on the lead's laptop (step 3 refuses a mismatch) and copy it (step 8). |
| The queue is empty or shows a "data mismatch" | The database and the generated files disagree. Back up, then `sudo -u credlens python3 tasks.py data --reset-db` (this removes decisions). |
| `df -h` shows the disk full | Delete old backups in `/opt/credlens/data/backups`. |

## Part E: no internet at the venue (the fallback demo, on a laptop)

If the venue's internet fails, the demo runs on one laptop with no internet at all. One command starts the
API (30 to 60 seconds) and serves the dashboard and the API on one local address, the way Nginx does on the
server:

```
python deploy/offline_demo.py
```

You should see `READY after ... s`, then `CredLens is running, offline, at http://localhost:8765/`, and the
browser opens on it. Stop with Ctrl+C: it stops the API it started too. It listens on this laptop only and
has no password. Options: `--no-browser`, `--port 9000` (another port for the dashboard).

**Get the laptop ready before the event, while there is internet** (about 15 minutes, once):

1. `git switch main`, `git pull`, then `python tasks.py setup`.
2. `python tasks.py data` (about 2 minutes).
3. The trained model. On the lead's laptop it is already there. On any other laptop **do not run
   `python tasks.py train`** (it makes a model the cards do not describe): copy the lead's folder
   `src/model/artifacts/synthetic_bd/` into the same place.
4. The built dashboard: `cd web`, `npm ci`, `npm run build` (needs Node.js and internet, once). Or take the
   bundle from Part A step 3 and unpack it in the project folder: `tar -xzf credlens-upload.tar.gz`, which puts
   both the dashboard (`web/dist`) and the model in place.
5. Check: `python -m src.api.preflight`. Only `OK` lines.

**Rehearse with the Wi-Fi switched off**, at least once, the day before: run the command above, open a merchant,
record a decision, switch the language, open the model card. Then `python tasks.py backup`.

What is different offline, and why it is fine:

- **Fonts.** The dashboard asks Google for its fonts (IBM Plex, Noto Sans Bengali). The offline server leaves those
  lines out so the page does not wait for a network that is not there, and the text uses the laptop's own
  fonts (Bangla included). It looks a little different; it works.
- **Decisions are recorded in the laptop's own database** (`data/app.db`). To begin the demo clean:
  `python tasks.py backup`, then `python tasks.py data --reset-db` (this removes every decision and audit entry).
- **Nothing else needs the internet.** No Docker, no Node.js and no account is needed at demo time. The five
  model cards are in the repository, so the model-card tabs work.

| What you see | What to do |
|---|---|
| `Not ready:` and a list | Each line names the command to run (setup, data, train, or build the dashboard). |
| The API did not become ready | Read `data/offline_demo_api.log`. A program already using port 8000 is the usual reason: close it. |
| The page says "CredLens is starting" | The API is still starting; the page tries again every 5 seconds. |
| Port 8765 is in use | `python deploy/offline_demo.py --port 9000` |

## What was tested, and what was not

Tested before this guide was handed over (Humayra's laptop, Oct 16):

- Steps 6 to 10 in a clean `ubuntu:22.04` container: `apt install`, `python3 tasks.py setup`, `data`, the
  preflight check, the API started the way the service starts it (ready after 36 seconds, `/docs` is a 404 in
  production mode), the data and the model card files.
- Step 11 to 12 in the same container: the real `deploy/nginx/credlens.conf`, `nginx -t`, the password (401 without,
  200 with), the API through Nginx.
- The self-signed HTTPS commands of step 13 in a clean container.
- The offline demo (Part E) with the real API and the built dashboard: the dashboard, the queue, a score and a
  merchant page through it, and Ctrl+C stopping both the page server and the API (found and fixed: on Windows
  an `Event().wait()` ignores Ctrl+C). It was not run with the Wi-Fi really switched off: rehearse that.
- The same Nginx file in Docker with the built dashboard and the running API (`python deploy/test_nginx_local.py`,
  35 checks), and the dashboard in a headless Edge browser behind it.

**Not tested** (needs a real server): `systemd` (the service file is checked for its contents only),
`certbot` with a real domain, the provider's firewall, and `scp` to a real server. If one of those steps
behaves differently, the "when something is wrong" table is the first place to look; tell Humayra what you saw.

## What this setup is, and is not

- **A demo.** The user name and password protect the whole site. The role switch in the sidebar (Officer,
  Admin, Viewer) is not a login: anyone who is past the site password can pick any role. Say so if a judge asks.
- **Synthetic data only.** The server holds no raw public file and no real merchant data.
- **One server, one SQLite file.** No shared online database was set up. The database's rule that decisions and
  audit entries can only be added (never changed or removed) is enforced by the application and by triggers in
  SQLite; those are covered by tests. The PostgreSQL version of those triggers has not been run.
- **No automatic approval or decline** anywhere. The site is decision support; the officer decides.
