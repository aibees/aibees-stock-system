import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import AutoImport from 'unplugin-auto-import/vite';
import AutoComponent from 'unplugin-vue-components/vite';

const path = require('path')
const env = loadEnv('', process.cwd());

// https://vitejs.dev/config/
export default defineConfig({
  define: {
    aibeesGlobal: {
      API_SERVER_URL : env.VITE_SERVER_URL,
      API_REDIRECT_URL : env.VITE_REDIRECT_URL,
      SERVICE_KEY : env.VITE_SERVICE_KEY,
      ENCRYPT_KEY : env.VITE_ENCRYPT_KEY,
      BATCH_SERVER_URL : env.VITE_BATCH_SERVER_URL
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@@': path.resolve(__dirname, './sass'),
      '@image': path.resolve(__dirname, './src/img'),
      '@scripts': path.resolve(__dirname, './src/scripts')
    }
  },
  server: {
    proxy : {
      "/ROOT" : {
        target : 'http://127.0.0.1:5556/',
        changeOrigin : true,
        logLevel : 'debug'
      },
      "/oauth2.0": {
        target: "https://nid.naver.com/",
        changeOrigin: true,
        logLevel: "debug",
      },
      "/v1": {
        target: "https://openapi.naver.com/",
        changeOrigin: true,
        logLevel: "debug",
      }
    },
    host: '0.0.0.0',
    port: 19010,

    watch: {
      usePolling: true
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        api: 'modern'
      }
    }
  },
  plugins: [
    vue(),
    AutoImport({
      imports: [
        'vue',
        'vue-router'
      ],
      dts: 'src/auto-imports.d.ts' // 자동 타입 선언 파일 경로
    }),
    AutoComponent({
      dirs: ['src/components/common/comp'],
      dts: 'src/auto-components.d.ts' // 자동 타입 선언 파일 경로
    })
  ]
})