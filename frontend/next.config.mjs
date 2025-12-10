/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  allowedDevOrigins: [
    'http://192.168.1.59:3000',
    'http://172.16.8.78:3000',
    'http://localhost:3000',
  ],
}

export default nextConfig
