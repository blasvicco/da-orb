FROM python:3.13-rc-alpine

ENV ESSENTIAL_PACKAGES="curl-dev gcc musl-dev" \
    UTILITY_PACKAGES=""

RUN apk update && \
    apk --no-cache --progress add $ESSENTIAL_PACKAGES $UTILITY_PACKAGES

COPY app/backend/requirements.txt /home/app/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /home/app/requirements.txt

COPY app/backend /home/app

WORKDIR /home/app

COPY hub/python/entrypoint.sh /usr/sbin/entrypoint.sh
ENTRYPOINT ["/usr/sbin/entrypoint.sh"]
