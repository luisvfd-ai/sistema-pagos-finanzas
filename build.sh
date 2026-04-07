#!/usr/bin/env bash
set -o errexit

echo "=== ARBOL REPO: pagos/static ==="
find pagos/static -print | sort || true

echo "=== ARBOL REPO: templates pagos ==="
find pagos/templates/pagos -print | sort || true

pip install -r requirements.txt

echo "=== FINDSTATIC LOCAL EN BUILD ==="
python manage.py findstatic pagos/js/reportes.js --verbosity 2 || true
python manage.py findstatic pagos/css/reportes.css --verbosity 2 || true

python manage.py collectstatic --noinput --clear

echo "=== ARBOL staticfiles DESPUES DE collectstatic ==="
find staticfiles -print | sort || true

echo "=== SOLO COINCIDENCIAS reportes ==="
find . -print | sort | grep -i reportes || true

python manage.py migrate