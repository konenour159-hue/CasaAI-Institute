# Image de développement (hot-reload via `vite dev`). Une image de
# production (build statique servi par Nginx, cf. §13 cahier technique)
# viendra remplacer celle-ci au moment du déploiement.
FROM node:22-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
