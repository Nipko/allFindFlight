# Despliegue en VPS con Portainer + Cloudflare Tunnel

Stack: Postgres + Redis + Backend (FastAPI) + Worker (Celery) + Frontend (Next.js) + cloudflared.
Dominio público: `planetour.cloud`. Sin puertos expuestos al host: todo el tráfico entra vía Cloudflare Tunnel.

---

## 1. Prerrequisitos

- VPS con Docker + Portainer instalados.
- Dominio `planetour.cloud` activo en Cloudflare (DNS apuntando a Cloudflare, modo "Full" recomendado).
- Cloudflare Zero Trust habilitado (gratis hasta 50 usuarios).
- Imágenes de las apps publicadas en un registry accesible desde el VPS (GHCR, Docker Hub, registry privado).

## 2. Construir y publicar imágenes

Desde tu máquina o un runner CI:

```bash
# Backend
docker build -t ghcr.io/nipko/allfind-backend:latest ./backend
docker push ghcr.io/nipko/allfind-backend:latest

# Frontend
docker build -t ghcr.io/nipko/allfind-frontend:latest ./frontend
docker push ghcr.io/nipko/allfind-frontend:latest
```

Si el VPS necesita autenticarse contra GHCR/Docker Hub, configurar credenciales en Portainer en
**Registries**.

> Más adelante conviene mover esto a GitHub Actions para builds automáticos en cada push a `main`.

## 3. Crear el Cloudflare Tunnel

1. Cloudflare dashboard → **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**.
2. Conector: **Cloudflared**. Nombre: `planetour-vps`.
3. En el paso "Install connector" copia el **token** (cadena larga `eyJ...`). No descargues nada — el contenedor `cloudflared` del stack hace el trabajo.
4. En **Public Hostnames** del tunnel, añade:

   | Subdomain | Domain          | Service                  |
   | --------- | --------------- | ------------------------ |
   | (vacío)   | planetour.cloud | `http://frontend:3000`   |
   | www       | planetour.cloud | `http://frontend:3000`   |

   El service name `frontend` resuelve dentro de la red Docker `internal`.

5. Cloudflare crea automáticamente registros CNAME en tu zona DNS apuntando al tunnel. No tocar.

## 4. Desplegar el stack en Portainer

### Opción A — Repositorio Git (recomendada)

1. Portainer → **Stacks** → **Add stack**.
2. Nombre: `allfindflight`.
3. **Build method**: *Repository*.
4. Repository URL: `https://github.com/Nipko/allFindFlight`.
5. Reference: `refs/heads/main`.
6. Compose path: `infra/docker-compose.prod.yml`.
7. **Environment variables** → cargar desde el archivo `.env.prod` o pegar manualmente:
   - `POSTGRES_PASSWORD`
   - `TUNNEL_TOKEN`
   - `REGISTRY` (si no usas el default `ghcr.io/nipko`)
   - `IMAGE_TAG` (default `latest`)
   - APIs opcionales: `GOOGLE_MAPS_API_KEY`, `AMADEUS_CLIENT_ID`, etc.
8. **Deploy the stack**.

### Opción B — Web editor

Pegar el contenido de `infra/docker-compose.prod.yml` directamente en el editor de Portainer y
configurar las env vars. Útil para un primer despliegue manual.

## 5. Inicializar la base de datos

La primera vez (o tras un reset de volumen) hay que cargar los aeropuertos:

En Portainer → contenedor `allfind-backend` → **Console** → conectar con shell `/bin/sh`:

```sh
python -m app.scripts.seed_airports
```

Tarda ~30 segundos. El comando es idempotente.

## 6. Verificación

- `https://planetour.cloud` debería cargar el frontend.
- `https://planetour.cloud/api/search?origin=MAD&destination=BCN&departure=2026-07-15` debería responder JSON.
- `https://planetour.cloud/api/../health` (proxiado por Next.js) → `{"status":"ok"}`.

Logs en Portainer: contenedor → **Logs** (cloudflared, backend, worker, frontend).

## 7. Actualizaciones

Tras un push a `main` con cambios, build de las nuevas imágenes y en Portainer:
- Stacks → `allfindflight` → **Pull and redeploy** (si está enlazado al repo).
- O bien `Stacks → allfindflight → Editor → Update the stack` con `Re-pull image` activado.

## 8. Backups

Volúmenes a respaldar: `allfindflight_postgres-data`. Redis es cache + cola, no necesita backup.

```bash
# en el VPS
docker run --rm -v allfindflight_postgres-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/postgres-$(date +%F).tgz -C /data .
```

## 9. Seguridad

- Ningún puerto está publicado al host (`ports:` ausente en todos los servicios). El único acceso público es vía Cloudflare Tunnel.
- Cloudflare puede añadir WAF, rate limiting y Access (autenticación de email para acceso restringido) sin tocar el stack.
- Postgres y Redis solo son alcanzables desde la red Docker `internal`.
- Rotar `POSTGRES_PASSWORD` y `TUNNEL_TOKEN` regularmente. Ambos viven solo en variables de entorno de la stack en Portainer.
