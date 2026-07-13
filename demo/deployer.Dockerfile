FROM alpine:3.20

# Static Go binary, no runtime deps; alpine stays tiny (~10 MB).
# busybox provides sh, cat, mkdir, date, printf, trap, sed,
# usr/bin/time -- all the shell utilities the lifecycle script uses.

ENV FIRECTL_HOME=/opt/firectl \
    FORCE_COLOR=1

WORKDIR /work

COPY firectl /usr/local/bin/firectl
COPY demo/lifecycle.sh /usr/local/bin/lifecycle.sh

# busybox lacks /usr/bin/time; install the GNU tool so the script's
# timing report during deployment works. (~200 KB)
RUN apk add --no-cache --quiet coreutils \
 && chmod +x /usr/local/bin/firectl /usr/local/bin/lifecycle.sh \
 && firectl --help >/dev/null 2>&1 \
 && grep -q cleanup /usr/local/bin/lifecycle.sh

ENTRYPOINT ["/usr/local/bin/lifecycle.sh"]