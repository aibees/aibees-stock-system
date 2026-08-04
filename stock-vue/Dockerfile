# ---- Build Stage ----
FROM node:20-alpine AS builder

WORKDIR /app
COPY . .

# build env file
ARG VITE_ENV=prd
ENV VITE_ENV=$VITE_ENV

# copy .env file
RUN cp .env.${VITE_ENV} .env

RUN yarn install && yarn build

# ---- Serve  Stage ----
FROM nginx:latest
LABEL maintainer="AIBEES <qwt0326@gmail.com>"

COPY --from=builder /app/dist /usr/share/nginx/html
COPY ./nginx.conf /etc/nginx/nginx.conf
COPY ./conf.d /etc/nginx/conf.d

EXPOSE 5556
