ARG BUILD_FROM=jellyfin/jellyfin:12.4
FROM ${BUILD_FROM}

# Persist Jellyfin state in the add-on data directory (/data).
ENV JELLYFIN_DATA_DIR=/data \
    JELLYFIN_CONFIG_DIR=/data/config \
    JELLYFIN_LOG_DIR=/data/log \
    JELLYFIN_CACHE_DIR=/data/cache

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
