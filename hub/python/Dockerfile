FROM rust:alpine AS renderer-builder

RUN apk --no-cache add musl-dev

COPY app/renderer /build/renderer
RUN cd /build/renderer && cargo build --release

FROM python:3.13-rc-alpine

ENV ESSENTIAL_PACKAGES="curl-dev gcc musl-dev" \
    UTILITY_PACKAGES=""

RUN apk update && \
    apk --no-cache --progress add $ESSENTIAL_PACKAGES $UTILITY_PACKAGES

COPY --from=renderer-builder /build/renderer/target/release/orb-report-render /usr/local/bin/orb-report-render

COPY app/backend/requirements.txt /home/app/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /home/app/requirements.txt

COPY app/backend /home/app

WORKDIR /home/app

COPY hub/python/entrypoint.sh /usr/sbin/entrypoint.sh
ENTRYPOINT ["/usr/sbin/entrypoint.sh"]
