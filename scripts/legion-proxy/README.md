# legion-proxy

Local Traefik for the Venture Studio runtime layer (backlog task-824, section 6.6).

- Network: `legion` (external; `docker network create legion`).
- Entry: `http://127.0.0.1:8888`, routing by `Host(...)` labels.
- Hostnames: `<app>.<env>.legion.localhost` (browser-native loopback resolution).
  For curl: `curl -H 'Host: living-library.dev.legion.localhost' http://127.0.0.1:8888/`.
- Opt in per service with `traefik.enable=true`, a router `rule`, and a
  `loadbalancer.server.port`; attach the service to the `legion` network.
- Studio identity labels: `legion.venture`, `legion.app`, `legion.env`, `legion.host`.

Start: `docker compose -p legion-proxy -f scripts/legion-proxy/compose.yml up -d`
Stop:  `docker compose -p legion-proxy stop`
