sudo apt update && sudo apt upgrade -y

sudo apt install -y ca-certificates curl gnupg git wget

curl -fsSL https://get.docker.com -o get-docker.sh

sudo sh get-docker.sh

sudo systemctl enable docker

sudo systemctl start docker

sudo usermod -aG docker "$USER"

if [ -d "$HOME/luminaire-control-deploy" ]; then cd "$HOME/luminaire-control-deploy"; git reset --hard; git pull --rebase; else; git clone "https://github.com/nishanthamabati/luminaire-control-deploy.git" "$HOME/luminaire-control-deploy"; cd "$HOME/luminaire-control-deploy"; fi

[ -d "$HOME/luminaire-control-deploy" ] && (cd "$HOME/luminaire-control-deploy" && git reset --hard && git pull --rebase) || git clone "https://github.com/nishanthamabati/luminaire-control-deploy.git" "$HOME/luminaire-control-deploy" && cd "$HOME/luminaire-control-deploy"

mkdir -p "$HOME/luminaire-control-deploy" && cd "$HOME/luminaire-control-deploy" && ( [ -d .git ] && { git reset --hard; git pull --rebase; } || { git clone "https://github.com/nishanthamabati/luminaire-control-deploy.git" . ; } )

docker compose up -d --remove-orphans