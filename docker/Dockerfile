FROM ghcr.io/puppeteer/puppeteer:latest

# Install color emoji fonts
USER root
RUN apt-get update && apt-get install -y \
    fonts-noto-color-emoji \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Switch back to pptruser
USER pptruser

WORKDIR /home/pptruser/project

ENTRYPOINT ["node", "convert.js"]