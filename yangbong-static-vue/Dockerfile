# ---- Build Stage ----
FROM node:22-alpine AS builder

WORKDIR /app
COPY . .

# API 호출이 없는 정적 페이지라 .env 복사 단계가 없다(yangbong-store-vue 와 다른 점).
RUN yarn install && yarn build

# ---- Serve  Stage ----
FROM nginx:latest
LABEL maintainer="AIBEES <qwt0326@gmail.com>"

COPY --from=builder /app/dist /usr/share/nginx/html
COPY ./nginx.conf /etc/nginx/nginx.conf
COPY ./conf.d /etc/nginx/conf.d

EXPOSE 5557
