FROM vikunja/vikunja:latest

USER root
RUN mkdir -p /app/vikunja/files /app/vikunja/.cache && \
    chown -R 1000:0 /app/vikunja/files /app/vikunja/.cache && \
    chmod -R 775 /app/vikunja/files /app/vikunja/.cache
USER 1000

EXPOSE 3456
