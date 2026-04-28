# Despliegue: VPS Ubuntu nativo + Cloudflare Tunnel

Stack: Postgres + Redis + Backend (FastAPI) + Worker (Celery) + Frontend (Next.js) + cloudflared.
Hostname público sugerido: **`vuelos.planetour.cloud`** (alias opcional `vuelos-ops.planetour.cloud`).
Postgres interno en `55432`, Redis en `56379` para no chocar con otros stacks del VPS.
Sin puertos publicados al host: todo el ingress entra por Cloudflare Tunnel.

---

## 0. Hostnames sugeridos

| Subdominio | Apunta a | Uso |
|---|---|---|
| `vuelos.planetour.cloud` | `http://frontend:3000` | App principal |
| `vuelos-ops.planetour.cloud` | `http://frontend:3000` | Alias opcional |

> El backend no necesita subdominio: el frontend Next.js reenvía `/api/*` al servicio `backend` por la red Docker interna.

---

## 1. Bootstrap del VPS (Ubuntu 22.04 / 24.04 limpio)

Instala Docker + Compose plugin, clona el repo en `/opt/allfindflight`, crea `infra/.env.prod` y configura UFW (solo SSH):

```bash
curl -fsSL https://raw.githubusercontent.com/Nipko/allFindFlight/main/infra/setup-vps.sh | sudo bash
```

Cuando termine, edita el archivo de variables:

```bash
sudo nano /opt/allfindflight/infra/.env.prod
```

Mínimo a rellenar:
```
POSTGRES_PASSWORD=<contraseña-fuerte>
TUNNEL_TOKEN=<token-de-cloudflare>
```

Opcionales: `GOOGLE_MAPS_API_KEY`, `AMADEUS_CLIENT_ID`, `AMADEUS_CLIENT_SECRET`, `TRAVELPAYOUTS_TOKEN`, `PROXY_URL`, `REGISTRY` (default `ghcr.io/nipko`), `IMAGE_TAG` (default `latest`).

---

## 2. GitHub Actions: variables y secretos

**Variables a configurar: NINGUNA.** El workflow usa `GITHUB_TOKEN` auto-provisionado.

Lo único, una sola vez:

1. Repo → **Settings → Actions → General → Workflow permissions** → **Read and write permissions**.
2. Tras el primer build exitoso: GitHub → tu perfil → **Packages** → `allfind-backend` → **Package settings → Change visibility → Public**. Repetir con `allfind-frontend`. *(Esto evita autenticar el VPS contra GHCR.)*

Si prefieres mantenerlas privadas: crear un PAT con `read:packages` y en el VPS:
```bash
echo "<PAT>" | sudo docker login ghcr.io -u <github-user> --password-stdin
```

---

## 3. Cloudflare Tunnel

1. Cloudflare Dashboard → **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**.
2. Connector: **Cloudflared**. Nombre sugerido: `planetour-vps`.
3. En "Install connector", **copia el token** (`eyJ...`). No descargues nada — el contenedor `cloudflared` del stack lo usa.
4. **Public Hostnames** del tunnel:

   | Subdomain | Domain | Service |
   |---|---|---|
   | `vuelos` | `planetour.cloud` | `http://frontend:3000` |
   | `vuelos-ops` | `planetour.cloud` | `http://frontend:3000` |

5. Cloudflare crea automáticamente los CNAME en tu zona DNS. No tocar nada más.

Pegar el token en `/opt/allfindflight/infra/.env.prod` como `TUNNEL_TOKEN`.

---

## 4. Levantar el stack

```bash
sudo /opt/allfindflight/infra/deploy.sh
```

Hace `git pull`, `docker compose pull`, `docker compose up -d`.

---

## 5. Inicializar la base de datos (una sola vez)

```bash
sudo docker exec -it aff-backend python -m app.scripts.seed_airports
```

Carga ~10k aeropuertos comerciales con índice H3. Idempotente.

---

## 6. Verificación

- `https://vuelos.planetour.cloud` → frontend.
- `https://vuelos.planetour.cloud/api/search?origin=MAD&destination=BCN&departure=2026-07-15` → JSON.
- Logs de un servicio:
  ```bash
  sudo docker logs -f aff-cloudflared
  sudo docker logs -f aff-backend
  ```
  Empezar por `aff-cloudflared` — debe decir "Registered tunnel connection".

---

## 7. Updates

Cada push a `main` dispara el workflow → publica `:latest` y `:sha-xxxxxxx` en GHCR. Para aplicar en el VPS:

```bash
sudo /opt/allfindflight/infra/deploy.sh
```

Para fijar versión / rollback: editar `IMAGE_TAG` en `.env.prod` a un sha concreto y volver a correr `deploy.sh`.

### Auto-update opcional (Watchtower)

Si quieres que el VPS pull cada N minutos sin intervención, añadir a la lista de servicios del compose:

```yaml
  watchtower:
    image: containrrr/watchtower
    container_name: aff-watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 300 --cleanup aff-backend aff-worker aff-frontend
```

---

## 8. Backups

Solo Postgres importa. Redis es cache + cola, no se respalda.

```bash
sudo docker run --rm \
  -v allfindflight_aff-postgres-data:/data \
  -v "$(pwd)":/backup alpine \
  tar czf /backup/aff-postgres-$(date +%F).tgz -C /data .
```

> Nombre del volumen: `<directorio-del-proyecto>_aff-postgres-data`. En `/opt/allfindflight` será `allfindflight_aff-postgres-data`. Verificar con `sudo docker volume ls`.

---

## 9. Comandos útiles

```bash
# Estado del stack
sudo docker compose -f /opt/allfindflight/infra/docker-compose.prod.yml \
     --env-file /opt/allfindflight/infra/.env.prod ps

# Reiniciar un servicio
sudo docker restart aff-backend

# Ver consumo
sudo docker stats --no-stream

# Apagar todo
sudo docker compose -f /opt/allfindflight/infra/docker-compose.prod.yml \
     --env-file /opt/allfindflight/infra/.env.prod down

# Apagar y borrar volúmenes (CUIDADO: pierde la DB)
sudo docker compose -f /opt/allfindflight/infra/docker-compose.prod.yml \
     --env-file /opt/allfindflight/infra/.env.prod down -v
```

---

## 10. Coexistencia con otros stacks en el mismo VPS

Garantizado por:
- Postgres en `55432`, Redis en `56379` (no 5432/6379).
- Containers prefijados `aff-*`.
- Volúmenes prefijados `aff-*`.
- Red Docker dedicada `aff-internal`.
- Sin puertos publicados al host.
- Hostname `vuelos.planetour.cloud` (no `api`/`admin`/`app`/raíz).
