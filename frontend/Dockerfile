FROM node:22-bookworm-slim AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
ENV VITE_API_BASE_URL=""
RUN pnpm build

FROM caddy:2-alpine
COPY --from=build /app/build /srv
