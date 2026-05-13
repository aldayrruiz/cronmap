# Cronmap

`cronmap` es un script Python para ejecutar escaneos de Nmap por lotes con estado persistente y control de ventana horaria.

## Características

- Divide `targets.txt` en lotes según `batch_size`.
- Guarda el estado en una base de datos SQLite (`state.db`).
- Permite reanudar escaneos cuando se interrumpe el proceso.
- Solo ejecuta escaneos dentro del horario configurado (`start_time` / `end_time`).
- Ejecuta lotes **de forma continua** sin pausas entre ellos hasta completar todos.
- Genera salidas XML en la carpeta configurada (`results/`).
- **Fusiona todos los XMLs** en un único archivo `merged.xml` con estadísticas consolidadas.
- **Genera reportes HTML** automáticamente a partir del XML fusionado.

## Archivos principales

- `scanner.py`: script principal que gestiona la inicialización, el progreso, la ejecución de Nmap y la generación de reportes.
- `merge.py`: módulo para fusionar múltiples archivos XML de Nmap (integrado en `scanner.py`).
- `config.json`: configuración del tamaño de lote, ventana horaria, argumentos de Nmap, directorio de salida e intervalo de verificación.
- `targets.txt`: lista de IPs a escanear, una IP por línea.
- `results/`: carpeta donde se almacenan los reportes `scan_<batch_id>.xml`, `merged.xml` y `results.html`.

## Requisitos

- Python 3
- Nmap instalado y accesible en el PATH
- lxml (instalable con `pip install lxml`)
- xsltproc (para generar reportes HTML)

### Instalación de dependencias

```bash
# Sistema
sudo apt-get install nmap xsltproc

# Python
pip install lxml
```

## Uso

### 1. Configuración inicial

Configurar `config.json` con los valores deseados:

```json
{
  "batch_size": 20,
  "start_time": "08:00",
  "end_time": "20:00",
  "nmap_args": "--privileged -sS -n -v -p- -Pn -T5 --open",
  "output_dir": "results",
  "check_interval_in_seconds": 1
}
```

**Parámetros:**
- `batch_size`: número de IPs por lote
- `start_time` / `end_time`: ventana horaria permitida (formato HH:MM)
- `nmap_args`: argumentos pasados a Nmap
- `output_dir`: directorio de salida para XMLs y reportes
- `check_interval_in_seconds`: intervalo en segundos para verificar si se sigue dentro de la ventana horaria (personalizable por el usuario)

### 2. Agregar objetivos

Editar `targets.txt` y agregar las IPs a escanear, una por línea:

```
192.168.0.1
192.168.0.2
192.168.0.3
```

### 3. Inicializar la base de datos

```bash
python3 scanner.py init
```

Esto crea la base de datos SQLite y divide los objetivos en lotes.

### 4. Ejecutar escaneos

```bash
python3 scanner.py run
```

El script ejecutará los lotes de forma continua, uno tras otro, respetando la ventana horaria configurada. Si se sale del horario permitido, pausa y espera a la próxima ventana.

### 5. Consultar el progreso

```bash
python3 scanner.py status
```

Muestra el progreso general, cantidad de lotes completados, pendientes y ETA estimado.

### 6. Generar reportes consolidados

Una vez completados todos (o algunos) escaneos, genera un reporte HTML:

```bash
python3 scanner.py html
```

Este comando:
- Fusiona todos los archivos `scan_*.xml` en `results/merged.xml`
- Consolida las estadísticas de todos los escaneos
- Incluye **todas las IPs escaneadas** en el atributo `args` del XML fusionado
- Genera un reporte HTML interactivo en `results/results.html`

## Flujo de trabajo típico

```bash
# 1. Preparar configuración y objetivos
# (Editar config.json y targets.txt)

# 2. Inicializar
python3 scanner.py init

# 3. Ejecutar escaneos (continuo)
python3 scanner.py run

# 4. Verificar progreso en otra terminal
python3 scanner.py status

# 5. Generar reportes finales
python3 scanner.py html
```

## Manejo de interrupciones

- Si se interrumpe un escaneo con `Ctrl+C`, el lote se marca como pendiente.
- El próximo `python3 scanner.py run` reanudará desde donde se pausó.
- Si se excede la ventana horaria configurada, el sistema pausa y reanuda automáticamente.

## Notas importantes

- El script **ejecuta lotes de forma continua** sin parar entre ellos.
- La ventana horaria se verifica cada `check_interval` segundos (configurable en `config.json`).
- Los resultados XML parciales de cada lote se guardan en `results/`.
- El XML fusionado contiene todas las IPs de todos los scans en el atributo `args`.
- Los reportes HTML se generan usando la hoja de estilos estándar de Nmap.
- Si no se ha ejecutado `init` antes de usar `run` o `status`, se mostrará un mensaje de error amigable.

## Troubleshooting

**Error: xsltproc no está instalado**
```bash
sudo apt-get install xsltproc
```

**Error: La base de datos no está inicializada**
```bash
python3 scanner.py init
```

**Error: No se encontraron archivos XML para fusionar**
Ejecuta primero `python3 scanner.py run` para generar los escaneos.

## Personalización

- `batch_size`: número de IPs por lote.
- `nmap_args`: argumentos pasados a Nmap.
- `output_dir`: directorio donde se generan los XML.
- `start_time` y `end_time`: horas de ejecución permitidas.
