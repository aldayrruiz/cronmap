# Cronmap

`cronmap` es un script Python para ejecutar escaneos de Nmap por lotes con estado persistente y control de ventana horaria.

## Características

- Divide `targets.txt` en lotes según `batch_size`.
- Guarda el estado en una base de datos SQLite (`state.db`).
- Permite reanudar escaneos cuando se interrumpe el proceso.
- Solo ejecuta escaneos dentro del horario configurado (`start_time` / `end_time`).
- Genera salidas XML en la carpeta configurada (`results/`).

## Archivos principales

- `scanner.py`: script principal que gestiona la inicialización, el progreso y la ejecución de Nmap.
- `config.json`: configuración del tamaño de lote, ventana horaria, argumentos de Nmap y directorio de salida.
- `targets.txt`: lista de IPs a escanear, una IP por línea.
- `results/`: carpeta donde se almacenan los reportes `scan_<batch_id>.xml`.

## Requisitos

- Python 3
- Nmap instalado y accesible en el PATH

## Uso

1. Instalar dependencias del sistema si es necesario:

```bash
sudo apt-get install nmap
```

2. Configurar `config.json` con los valores deseados.

3. Agregar las IPs a escanear en `targets.txt`.

4. Inicializar la base de datos y crear los lotes:

```bash
python3 scanner.py init
```

5. Ejecutar el siguiente lote pendiente o reanudar un lote en progreso:

```bash
python3 scanner.py run
```

6. Consultar el estado del progreso:

```bash
python3 scanner.py status
```

## Notas

- El script respeta la ventana horaria configurada y detiene los escaneos si se sale de ese intervalo.
- Los resultados se guardan como XML en `results/`.
- Si se interrumpe un escaneo manualmente, el lote se marca como pendiente para reanudación.

## Personalización

- `batch_size`: número de IPs por lote.
- `nmap_args`: argumentos pasados a Nmap.
- `output_dir`: directorio donde se generan los XML.
- `start_time` y `end_time`: horas de ejecución permitidas.
