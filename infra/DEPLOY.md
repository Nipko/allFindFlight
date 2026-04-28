# Despliegue: VPS Ubuntu + Portainer + Cloudflare Tunnel

Stack: Postgres + Redis + Backend (FastAPI) + Worker (Celery) + Frontend (Next.js) + cloudflared.
Hostname público sugerido: **`vuelos.planetour.cloud`** (alternativo: `vuelos-ops.planetour.cloud`).
Postgres interno en `55432`, Redis en `56379` para no chocar con otros stacks del VPS.
Sin puertos publicados al host: todo el ingress entra por Cloudflare Tunnel.

---

## 0. Hostnames sugeridos (no usar `api`/`admin` para evitar colisiones)

| Subdominio | Apunta a | Uso |
|---|---|---|
| `vuelos.planetour.cloud` | `http://frontend:3000` | App principal |
| `vuelos-ops.planetour.cloud` | `http://frontend:3000` | Alias para acceso restringido (opcional) |

> El backend no necesita subdominio propio: el frontend Next.js reenvía `/api/*` al servicio `backend` por la red Docker interna.

---

## 1. Bootstrap del VPS (Ubuntu 22.04/24.04 limpio)

Instala Docker + Portainer + UFW. Como root:

```bash
curl -fsSL https://raw.githubusercontent.com/Nipko/allFindFlight/main/infra/setup-vps.sh | sudo bash
```

Al terminar:
- Portainer en `https://<IP-VPS>:9443` (crea admin user en el primer acceso).
- UFW abierto solo para SSH y `9443/tcp`. Nada más.

---

## 2. GitHub Actions: variables y secretos

**Variables a configurar: NINGUNA.** El workflow `.github/workflows/build-images.yml` usa `GITHUB_TOKEN` (auto-provisionado) y publica las imágenes en GHCR.

Lo que SÍ tienes que hacer una sola vez:

1. **Permisos de Actions sobre el repo**
   - GitHub repo → Settings → Actions → General → "Workflow permissions" → marcar **Read and write permissions**.
   - Equivalente: el workflow ya pide `permissions: { packages: write }` por job, así que esto es redundante pero no estorba.

2. **Visibilidad de los packages publicados** (la primera vez que el workflow corre):
   - GitHub user → Packages → `allfind-backend` → Package settings → **Change visibility → Public**.
   - Repetir con `allfind-frontend`.
   - Esto evita tener que dar credenciales al VPS para `docker pull`.

3. **Si prefieres mantener las imágenes privadas:** configurar registry credentials en Portainer.
   - Crear un PAT en GitHub: Settings → Developer settings → Personal access tokens → **Classic** → `read:packages`.
   - Portainer → Registries → **Add registry** → "Custom" → URL `ghcr.io`, username = tu usuario GitHub, password = ese PAT.
   - El stack lo usará automáticamente al hacer pull.

> Resumen: si haces los packages públicos (recomendado para uso personal sin secretos en imagen), no necesitas configurar nada más.

---

## 3. Cloudflare Tunnel

1. Cloudflare Dashboard → **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**.
2. Connector: **Cloudflared**. Nombre sugerido: `planetour-vps`.
3. En "Install connector", **copia el token** (cadena `eyJ...`). No descargues nada — el contenedor `cloudflared` del stack hace el trabajo.
4. **Public Hostnames** del tunnel:

   | Subdomain | Domain | Service |
   |---|---|---|
   | `vuelos` | `planetour.cloud` | `http://frontend:3000` |
   | `vuelos-ops` | `planetour.cloud` | `http://frontend:3000` |

5. Cloudflare crea automáticamente los CNAME en tu zona DNS apuntando al tunnel.

---

## 4. Desplegar el stack en Portainer

1. Portainer → **Stacks** → **Add stack**.
2. Nombre: `allfindflight`.
3. **Build method**: *Repository*.
4. Repository URL: `https://github.com/Nipko/allFindFlight`.
5. Reference: `refs/heads/main`.
6. Compose path: `infra/docker-compose.prod.yml`.
7. **Environment variables**:
   ```
   POSTGRES_PASSWORD=<contraseña-fuerte>
   TUNNEL_TOKEN=<token-de-cloudflare>
   REGISTRY=ghcr.io/nipko        (opcional; este es el default)
   IMAGE_TAG=latest              (opcional)
   GOOGLE_MAPS_API_KEY=          (opcional, para tiempos de traslado)
   AMADEUS_CLIENT_ID=            (opcional)
   AMADEUS_CLIENT_SECRET=        (opcional)
   TRAVELPAYOUTS_TOKEN=          (opcional)
   PROXY_URL=                    (opcional, para scrapers)
   ```
8. Activa **Pull and redeploy** y **Re-pull image**.
9. **Deploy the stack**.

> Si `nipko` no es tu usuario de GitHub, ajusta `REGISTRY` (por ejemplo `ghcr.io/tu-usuario`).

---

## 5. Inicializar la base de datos

Una sola vez (o tras un reset de volumen):

Portainer → contenedor `aff-backend` → **Console** → conectar (`/bin/sh`):

```sh
python -m app.scripts.seed_airports
```

Carga ~10k aeropuertos comerciales con índice H3. Idempotente.

---

## 6. Verificación

- `https://vuelos.planetour.cloud` → frontend.
- `https://vuelos.planetour.cloud/api/search?origin=MAD&destination=BCN&departure=2026-07-15` → JSON con ofertas.
- Logs en Portainer: contenedor → **Logs**. Empezar por `aff-cloudflared` (debe decir "Registered tunnel connection").

---

## 7. Updates

Cada push a `main` dispara el workflow → publica `:latest` y `:sha-xxxxxxx` en GHCR.
Para aplicar:

- Portainer → Stacks → `allfindflight` → **Pull and redeploy**.
- O cambia `IMAGE_TAG` a un sha específico para fijar versión / hacer rollback.

---

## 8. Backups

Solo Postgres importa:

```bash
docker run --rm \
  -v allfindflight_aff-postgres-data:/data \
  -v $(pwd):/backup alpine \
  tar czf /backup/aff-postgres-$(date +%F).tgz -C /data .
```

Redis es cache + cola, no se respalda.

---

## 9. Coexistencia con otros stacks en el mismo VPS

Garantizado por:
- Postgres en `55432`, Redis en `56379` (no 5432/6379).
- Containers prefijados `aff-*`.
- Volúmenes prefijados `aff-*`.
- Red Docker dedicada `aff-internal`.
- Sin puertos publicados al host.
- Hostname `vuelos.planetour.cloud` (no `api`/`admin`/`app`/raíz).
