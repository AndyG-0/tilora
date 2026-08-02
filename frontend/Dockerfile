FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
# Read via SvelteKit's $env/dynamic/public (not $env/static/public), so this
# is resolved from the container's environment at request time rather than
# inlined into the client bundle at build time — it must be the address the
# *browser* can reach the backend at (e.g. the Pi's LAN IP), not an
# in-compose service name like "backend". Override with `-e` / compose
# `environment:` per deployment; no rebuild needed, and frontend/backend can
# run on different hosts.
ENV PUBLIC_API_BASE_URL=http://localhost:8000
COPY --from=build /app/build ./build

# node:20-alpine already ships an unprivileged "node" user (uid 1000) —
# use it instead of running the server as root.
RUN chown -R node:node /app
USER node

EXPOSE 3000

CMD ["node", "build/index.js"]
