FROM alpine:3.20
RUN apk add --no-cache autossh openssh-client
ENV RELAY_HOST="" \
    RELAY_FORWARD="api.proxyapi.ru:443"
CMD autossh -M 0 -N -T \
    -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new \
    -o ConnectTimeout=10 \
    -i /keys/id_ed25519 \
    -L 0.0.0.0:443:${RELAY_FORWARD} \
    root@${RELAY_HOST}
