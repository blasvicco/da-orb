#!/bin/sh
set -e
mkdir -p /home/app/media
# python manage.py collectstatic --noinput
python manage.py migrate --noinput
exec "$@"
