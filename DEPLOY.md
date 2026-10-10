# Deploying to the cloud

This puts the whole app on one small server, protected by HTTPS, using the free credit from the GitHub
Student Developer Pack. It takes a couple of hours the first time.

```
visitor --HTTPS--> Caddy (certificates, redirects) --> app container (FastAPI + the built React site) --> SQLite on a volume
```

Everything runs from one `docker compose up`. Only Caddy is exposed to the internet; the app can't be reached directly.

## What you need

- The GitHub Student Developer Pack, which includes **Azure for Students** (about $100 of credit, no credit card).
  Sign in at <https://azure.microsoft.com/free/students> with your school account.
- This repository on GitHub (it is).
- About 2 hours, and a terminal. On Windows, PowerShell already has `ssh`.

> Prices and student offers change. Check the price Azure shows you before you click Create, and look at
> **Cost Management** in the portal now and then.

---

## 1. Create the server (Azure portal)

**Virtual machines -> Create -> Azure virtual machine**

| Setting | Choose |
|---|---|
| Subscription | Azure for Students |
| Resource group | Create new: `stockwatcher-rg` (deleting this later removes everything and stops all charges) |
| Region | The nearest one your subscription allows. Student subscriptions restrict some regions and sizes, so if one isn't offered try another |
| Image | **Ubuntu Server 24.04 LTS** |
| Size | The cheapest with **2 GB of memory or more** (for example a B1ms). 1 GB works, but only with the swap file in step 3 |
| Authentication | **SSH public key**. Let Azure generate a key pair and **download the .pem file**, then keep it safe |
| Username | `azureuser` |
| Inbound ports | Allow **SSH (22), HTTP (80), HTTPS (443)** |

Then, on the **Networking** tab, next to the public IP choose **Create new** and set:

- **Assignment: Static**, so the address doesn't change when the VM restarts.
- After the VM exists: open the public IP resource -> **Configuration** -> add a **DNS name label**
  (for example `yourname-stocks`). Your free address is then
  `yourname-stocks.<region>.cloudapp.azure.com`. That name is what you'll use as `DOMAIN` below.

> If Caddy can't get a certificate for the Azure name (rare), use a free DuckDNS name or a domain from the Student Pack instead.
> Any name works as long as it points at the server's IP address.

## 2. Connect

```powershell
ssh -i C:\path\to\stockwatcher_key.pem azureuser@yourname-stocks.<region>.cloudapp.azure.com
```

If Windows complains the key is "UNPROTECTED", right-click the file -> Properties -> Security -> Advanced, remove
inheritance, and leave only your own user with read access.

## 3. Prepare the server (copy and paste)

```bash
# updates, and automatic security updates from now on
sudo apt update && sudo apt -y upgrade
sudo apt -y install unattended-upgrades ufw

# a swap file, so building the app can't run out of memory on a small server
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# firewall: only SSH, web and HTTPS. (Azure's own firewall is a second layer outside this one.)
sudo ufw default deny incoming && sudo ufw default allow outgoing
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp
sudo ufw --force enable

# confirm passwords can't be used to log in over SSH (it should say "no")
sudo sshd -T | grep -i passwordauthentication
```

If that last line says `yes`:

```bash
echo -e "PasswordAuthentication no\nPermitRootLogin no" | sudo tee /etc/ssh/sshd_config.d/00-hardening.conf
sudo sshd -t && sudo systemctl reload ssh
```

Optional but good: in the Azure portal, open the VM's **Networking** and change the SSH rule's source from "Any"
to **My IP address**. (If your home address changes later, edit it again.)

## 4. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit    # then ssh back in so the group change applies
```

## 5. Get the code

Public repository:

```bash
git clone https://github.com/YOUR-USER/YOUR-REPO.git StockWatcher && cd StockWatcher
```

Private repository, using a read-only deploy key:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N ""
cat ~/.ssh/deploy_key.pub     # GitHub repo -> Settings -> Deploy keys -> Add key (leave "write access" OFF)
GIT_SSH_COMMAND="ssh -i ~/.ssh/deploy_key -o IdentitiesOnly=yes" git clone git@github.com:YOUR-USER/YOUR-REPO.git StockWatcher
cd StockWatcher && git config core.sshCommand "ssh -i ~/.ssh/deploy_key -o IdentitiesOnly=yes"
```

## 6. Configure

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"     # copy this output
nano .env       # set DOMAIN=yourname-stocks.<region>.cloudapp.azure.com  and  SECRET_KEY=<the output>
chmod 600 .env
```

`.env` holds your secret key and is never committed to Git (it is in `.gitignore`).

## 7. Launch

```bash
docker compose up -d --build        # the first build takes a few minutes
docker compose ps                   # both should say "running" / "healthy"
docker compose logs -f caddy        # look for "certificate obtained successfully", then Ctrl+C
```

Open `https://YOUR-DOMAIN`. You should see the padlock, and `http://` should redirect to `https://`.

## 8. Create the accounts

```bash
# your own account (it asks for a password, 10+ characters)
docker compose exec app python -m app.create_user yourname

# a demo account with a realistic but fictional portfolio, for showing people
docker compose exec app python -m app.seed_demo
```

The second command prints the demo password once. Write it down. Use the demo account for the interview and keep
your real portfolio off the public server. To rebuild the demo data: `docker compose exec app python -m app.seed_demo --reset`.

## 9. Check it works

- [ ] The padlock shows, and `http://` redirects to `https://`
- [ ] Log in as the demo user; Holdings, Performance and Breakdown fill in
- [ ] Refresh on `/portfolio` (it should not 404)
- [ ] **Overview** loads. The first heatmap load takes a minute while company sizes are looked up
- [ ] Try five wrong passwords: you should get "Too many failed login attempts"
- [ ] Paste your address into <https://securityheaders.com> and <https://www.ssllabs.com/ssltest/> (ask for an A grade)

## 10. Backups

Everything lives in one SQLite file. Take nightly copies:

```bash
crontab -e      # add this line (keeps the newest 14 copies on the server):
0 3 * * * cd /home/azureuser/StockWatcher && docker compose exec -T app python -m app.backup >> /home/azureuser/backup.log 2>&1
```

A copy on the same server isn't enough if the server is lost, so occasionally pull one to your own machine:

```bash
# on the server
cd ~/StockWatcher && mkdir -p ~/backups && docker compose cp app:/data/backups/. ~/backups/
# on your PC (PowerShell)
scp azureuser@YOUR-DOMAIN:~/backups/* C:\path\to\backups\
```

To restore: `docker compose stop app`, copy the backup over `/data/stockwatcher.db` (for example with `docker compose cp`),
then `docker compose start app`.

## Updating after you change the code

```bash
cd ~/StockWatcher && git pull && docker compose up -d --build
```

Your data and certificates are in Docker volumes, so rebuilding doesn't touch them.

## The day before the interview

- Visit the site from your phone on mobile data (a different network to your own)
- Log in as the demo user, and open **Overview** once so the heatmap is already loaded
- Check `docker compose ps` is healthy, and that the Azure credit isn't about to run out
- Have the demo username and password somewhere safe, not in the repo
- Optional: set `ENABLE_DOCS=true` in `.env`, then `docker compose up -d`, to show the API docs at `/docs`

## If something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| Browser can't connect | Ports 80/443 not open in the Azure network rules, or the DNS name doesn't point at the VM's IP |
| Certificate error or `docker compose logs caddy` shows failures | `DOMAIN` in `.env` doesn't match the DNS name, or DNS hasn't spread yet. Wait a few minutes and `docker compose restart caddy` |
| 502 Bad Gateway | The app isn't healthy: `docker compose logs app` |
| App exits straight away with "SECRET_KEY" | `.env` is missing the key, or it is under 32 characters |
| Charts say "data provider had a problem" | Yahoo is rate-limiting or changed something. Wait, or update the library: `docker compose build --no-cache app && docker compose up -d` |
| Build is killed | Out of memory: make sure the swap file from step 3 exists (`free -h`) |

## Stopping the bill

- **Pause:** in the Azure portal, **Stop** the VM (it says "deallocated"). Compute charges stop; the disk and static IP still cost a little.
- **Remove everything:** delete the `stockwatcher-rg` resource group.

## Security summary (good to be able to explain)

| Concern | What the app does |
|---|---|
| Data in transit | HTTPS everywhere via Caddy and Let's Encrypt; HTTP redirects; HSTS header |
| Passwords | Hashed with argon2, never stored in plain text; 10+ characters required; length-capped inputs |
| Sessions | Signed cookie that is `HttpOnly`, `Secure`, `SameSite=Lax` and `__Host-` prefixed; 14-day lifetime |
| Guessing attacks | 5 failed logins per account (and 20 per visitor) lock for 15 minutes; failures are logged |
| Abuse of public endpoints | Per-visitor rate limits on everything, tighter on endpoints that call Yahoo |
| Cross-site attacks | Cross-site POST/PUT/DELETE refused; strict Content-Security-Policy; no CORS in production; clickjacking blocked |
| Data separation | Every portfolio query is filtered by the logged-in user; tested |
| Secrets | Secret key only from the environment, app refuses to start without it; `.env` never in Git or the image |
| Server | SSH by key only, firewall (22/80/443), automatic security updates, app runs as an unprivileged user with no extra Linux capabilities |
| Exposure | App port is not published; only Caddy is reachable; API docs off in production |
| Recovery | Nightly consistent SQLite backups, kept off-server occasionally |

**Honest limitations:** data at rest is protected by file permissions and the cloud provider's disk encryption, not
application-level encryption. Rate limits live in memory and reset on restart. Market data comes from Yahoo through an
unofficial library, which is fine for a personal project; a production product would use a licensed data provider.
