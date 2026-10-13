# Web image: node_modules are installed inside Linux (never the host's Mac/Windows ones) and the source is copied in,
# so there is no bind mount, no file-watch polling and no native-binding mismatch. Rebuild after code changes.
FROM node:22-slim
WORKDIR /app/web
COPY package.json package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY . .
ENV BROWSER=none
EXPOSE 5173
CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]
