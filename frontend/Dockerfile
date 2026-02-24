# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy WASM file for sql.js
COPY --from=builder /app/public/sql-wasm.wasm /usr/share/nginx/html/sql-wasm.wasm

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
