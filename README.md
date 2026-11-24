# Clínica Miramar — Portal Web & Portal de Pacientes (Entorno Local)

Aplicación web local sin dependencias de runtime en Python (biblioteca estándar de Python 3 + SQLite), con interfaz compilada en **Tailwind CSS v4** y tipografías variables **Plus Jakarta Sans** e **Inter** autoalojadas en `static/fonts/` para ejecución **100% offline** (incluyendo Kali Linux).

## Ejecución rápida (sin Node ni internet)

```bash
cd clinica-miramar
python3 app.py
```

Abrir en el navegador: `http://127.0.0.1:5000`

*(Opcional: `CLINICA_HOST=0.0.0.0 CLINICA_PORT=8080 python3 app.py`)*

## Ejecución con Docker (o Podman en Fedora)

Con **Docker Compose**:
```bash
docker compose up -d --build
```

O con **Docker CLI**:
```bash
docker build -t clinica-miramar:latest .
docker run --rm -p 127.0.0.1:5000:5000 --name clinica-miramar clinica-miramar:latest
```

En **Fedora** (usando `podman`, ya preinstalado):
```bash
podman build -t clinica-miramar:latest .
podman run --rm -p 127.0.0.1:5000:5000 --name clinica-miramar clinica-miramar:latest
```

Para **transportar la imagen 100% offline** a tu VM de Kali Linux:
```bash
docker save -o clinica-miramar-image.tar clinica-miramar:latest
# Dentro de Kali Linux:
docker load -i clinica-miramar-image.tar
docker run --rm -p 127.0.0.1:5000:5000 clinica-miramar:latest
```

*(Nota: la base SQLite dentro del contenedor se inicializa automáticamente en `/app/data/clinica.db`; al reiniciar el contenedor con `--rm`, el entorno vuelve siempre a su estado limpio inicial).*

## Recompilación de estilos (solo si modificas plantillas o `src/input.css`)

```bash
npm run build:css
```

## Cuentas de prueba precargadas

* **Paciente 1 (5 informes, ECG, Radiografía, Resonancia, 4 recetas, 5 boletas):** `ana.silva@miramar.local` / `Miramar2026!`
* **Paciente 2 (Resonancia Encéfalo, 2 recetas, 2 boletas):** `carlos.mendez@miramar.local` / `Salud2026!`

## Mapa de rutas

* `/` — Portada institucional, buscador con sugerencias, Bento Grid, especialistas, telemedicina y FAQ
* `/especialistas` — Directorio con filtros componibles (`?q=`, `?esp=`, `?modalidad=`)
* `/agendar` — Reserva real de horas médicas (`?specialist_id=...`)
* `/login` — Inicio de sesión al Portal de Pacientes
* `/paciente/panel` — Resumen clínico con alerta de alergias, KPIs, últimos informes, medicación y citas
* `/paciente/resultados` — Resultados de exámenes e imagenología con filtros por tipo y texto
* `/paciente/ficha?id=1001` — Informe clínico con tabla cuantitativa de rangos y visor DICOM/ECG con lightbox
* `/paciente/recetas` y `/paciente/receta?id=501` — Recetas médicas electrónicas imprimibles y órdenes pendientes
* `/paciente/pagos` — Bonos, cobertura previsional, copagos y comprobantes electrónicos
* `/paciente/perfil` — Ficha personal completa (domicilio, emergencia, alergias) y bitácora de actividad
* `/robots.txt` y `/internal/status` — Directivas y estado técnico local
