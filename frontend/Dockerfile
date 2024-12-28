# Build stage
FROM node:20-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies with clean install
RUN npm ci

# Copy all frontend files
COPY . .

# Copy the docker env file as .env.local for build
COPY .env.docker .env.local

# Set build-time environment variables
ARG NEXT_PUBLIC_API_URL=http://localhost:8090
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8090
ARG NEXT_PUBLIC_COLLECTION_ID_FDA=1
ARG NEXT_PUBLIC_COLLECTION_ID_EMA=2
ARG NEXT_PUBLIC_COLLECTION_ID_HTA_SWEDEN=3
ARG NEXT_PUBLIC_COLLECTION_ID_HTA_FRANCE=4
ARG NEXT_PUBLIC_COLLECTION_ID_HTA_GERMANY=5

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_COLLECTION_ID_FDA=$NEXT_PUBLIC_COLLECTION_ID_FDA
ENV NEXT_PUBLIC_COLLECTION_ID_EMA=$NEXT_PUBLIC_COLLECTION_ID_EMA
ENV NEXT_PUBLIC_COLLECTION_ID_HTA_SWEDEN=$NEXT_PUBLIC_COLLECTION_ID_HTA_SWEDEN
ENV NEXT_PUBLIC_COLLECTION_ID_HTA_FRANCE=$NEXT_PUBLIC_COLLECTION_ID_HTA_FRANCE
ENV NEXT_PUBLIC_COLLECTION_ID_HTA_GERMANY=$NEXT_PUBLIC_COLLECTION_ID_HTA_GERMANY

# Build the Next.js application
RUN npm run build

# Production stage
FROM node:20-alpine AS runner

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install only production dependencies
RUN npm ci --only=production

# Copy built application from builder stage
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.mjs ./
COPY --from=builder /app/tsconfig.json ./

# Create user to run the app
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001

# Change ownership
RUN chown -R nextjs:nodejs /app

USER nextjs

# Expose port
EXPOSE 3001

# Start the application
CMD ["npm", "start"]