FROM vikunja/vikunja:latest

USER 0
RUN mkdir -p /app/vikunja/files /app/vikunja/.cache && \
    chown -R 1000:0 /app/vikunja/files /app/vikunja/.cache && \
    chmod -R 777 /app/vikunja/files /app/vikunja/.cache
USER 1000

EXPOSE 3456
