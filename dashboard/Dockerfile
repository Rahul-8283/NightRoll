# Warden dashboard: build the static files, then serve them from nginx.
# The same nginx also terminates TLS and proxies /v1/ to the API; its configuration is infra/nginx/nightroll.conf,
# mounted by infra/docker-compose.yml. Only public values are built in (the Supabase anon key is public by design;
# the service role key never reaches this image).

FROM node:24-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=/v1
ARG VITE_WS_URL=/v1/ws/rooms
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_WS_URL=$VITE_WS_URL \
    VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
RUN npm run build

FROM nginx:1.28-alpine
# The image's own default site would fight the one in infra/nginx/nightroll.conf for port 80.
RUN rm -f /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80 443
