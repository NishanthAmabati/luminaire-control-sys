./generate_env.sh
set -a; source .env; set +a

redis:
luminaire_service: python3 luminaire_service/main.py
scheduler_service: python3 scheduler_service/main.py
state_service: python3 state_service/main.py
event_gw: cd event_gw; set -a; source ../.env; set +a; node src/server.mjs
webapp: 
docker build -t webapp -f webapp/Dockerfile . 
docker run --rm -p 80:80 --add-host host.docker.internal:host-gateway -v "$PWD/webapp/nginx.local.conf:/etc/nginx/conf.d/default.conf:ro" webapp