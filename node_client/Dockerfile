# Dockerfile.nodejsclient
FROM node:18-alpine

WORKDIR /app

# Copy package.json and package-lock.json (if available)
COPY package*.json ./

RUN npm install
# Install production dependencies
# Using npm ci for reproducible builds if package-lock.json is present
# --omit=dev ensures only production dependencies are installed (npm v7+)
# For older npm, use `npm install --production` after `npm ci` or just `npm install --production`
#RUN npm ci --omit=dev

# Copy the rest of the application source code
# This will include client_server.js and the templates/ directory
COPY . .

EXPOSE 3000

ENV NODE_ENV=production

CMD [ "node", "client_server.js" ]
