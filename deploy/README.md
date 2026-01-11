# Deployment

## VPS Setup

### 1. Install dependencies

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git
```

### 2. Clone and setup

```bash
cd /opt
sudo git clone --recurse-submodules <your-repo-url> ruokalista
cd ruokalista
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt
```

### 3. Setup systemd service

```bash
sudo cp deploy/ruokalista.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ruokalista
sudo systemctl start ruokalista
```

### 4. Check status

```bash
sudo systemctl status ruokalista
sudo journalctl -u ruokalista -f
```

## Git Sync Setup

For the sync feature to push changes:

```bash
# On VPS, setup SSH key for git
ssh-keygen -t ed25519 -f ~/.ssh/id_recipes

# Add public key to your git host (GitHub/GitLab)
cat ~/.ssh/id_recipes.pub

# Configure git in recipes submodule
cd /opt/ruokalista/reseptit
git config user.name "Ruokalista Bot"
git config user.email "bot@example.com"
```

## Updating

```bash
cd /opt/ruokalista
sudo git pull
sudo git submodule update --remote
sudo systemctl restart ruokalista
```
