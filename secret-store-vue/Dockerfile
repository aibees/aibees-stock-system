# ---- Build Stage ----
# @capacitor/cli 8.x는 node >=22 필요 (yarn install이 엔진 불일치 시 하드 실패함)
FROM node:22-alpine AS builder

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
