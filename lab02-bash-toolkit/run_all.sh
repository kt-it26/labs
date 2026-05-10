#!/bin/bash

# Asegurarse de que se ejecuta desde la carpeta del proyecto
cd "$(dirname "$0")"

# Crear carpeta de reports si no existe
mkdir -p reports

echo "=== Ejecutando logs ==="
python3 -m cli.main logs --dir /var/log --max-size 50 --keep 2 --compress

echo "=== Ejecutando backup ==="
mkdir -p ~/backup_test
python3 -m cli.main backup --src ~/ --dest ~/backup_test --compress --verify

echo "=== Ejecutando health (puertos locales) ==="
python3 -m cli.main health --ports 22,80,443 --host localhost

echo "=== Ejecutando inventory ==="
python3 -m cli.main inventory --output reports/inventory.json

echo "=== Ejecutando watchdog (SSH solo como ejemplo, requiere sudo) ==="
sudo python3 -m cli.main watchdog --services ssh --interval 10 --restart

echo "=== Generando reporte HTML ==="
python3 -m cli.main report --output reports/report.html --open

echo "=== Todo completado! Revisa reports/report.html ==="