FROM alpine:3.20

RUN apk add --no-cache ca-certificates curl unzip \
 && curl -fsSL -o /tmp/x.zip https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip \
 && unzip -q /tmp/x.zip -d /usr/local/bin \
 && chmod +x /usr/local/bin/xray \
 && rm -f /tmp/x.zip

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

ENV PORT=8080
ENV UUID=68133b31-4a2a-4ba3-9ad7-01783afc08e0
ENV WSPATH=/w104235bcdf

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
