import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import AutoImport from 'unplugin-auto-import/vite';
import AutoComponent from 'unplugin-vue-components/vite';

const path = require('path')

// aibeesGlobal(화면 전역)에 들어가는 값. 하나라도 비면 define 이 그 키를 빼버려서
// aibeesApi 의 baseURL 이 undefined 가 되고, 요청이 에러 없이 현재 origin 으로
// 날아간다(원인 찾기 매우 어려움). 그래서 빌드 시점에 끊는다.
const REQUIRED_ENV = [
  'VITE_SERVER_URL',
  'VITE_REDIRECT_URL',
  'VITE_SERVICE_KEY',
  'VITE_ENCRYPT_KEY',
  'VITE_BATCH_SERVER_URL',
];

// AdSense 스크립트(index.html 의 adsense:start ~ adsense:end)는 웹 운영 빌드에만 남긴다.
//   - dev 서버: 필요 없음(앱 cap:dev 도 dev 서버 화면을 그대로 띄운다)
//   - 앱 빌드(BUILD_TARGET=app, npm run build:app / cap:prod): 앱 WebView 안 AdSense 는 정책 위반 → 제거
const ADSENSE_BLOCK = /[ \t]*<!-- adsense:start[\s\S]*?<!-- adsense:end -->\n?/;
const adsenseWebOnly = (command) => ({
  name: 'adsense-web-only',
  transformIndexHtml(html) {
    const keep = command === 'build' && process.env.BUILD_TARGET !== 'app';
    return keep ? html : html.replace(ADSENSE_BLOCK, '');
  },
});

// https://vitejs.dev/config/
export default defineConfig(({ mode, command }) => {
  // [수정] loadEnv('') → loadEnv(mode)
  //   '' 를 넘기면 .env 하나만 읽혀서 .env.dev / .env.prd 는 **전혀 반영되지 않았다**.
  //   그래서 iOS 빌드 결과가 "그 순간 .env 에 무엇이 들어 있었는지"에 좌우됐고,
  //   dev URL 로 구워진 걸 뒤늦게 알아 TestFlight 에 다시 올리는 일이 생겼다.
  //   loadEnv(mode, ...) 는 .env → .env.local → .env.<mode> → .env.<mode>.local
  //   순으로 읽고 뒤쪽이 앞쪽을 덮는다. 즉 --mode prd 면 .env 상태와 무관하게
  //   .env.prd 가 최종값이 된다(= npm run cap:prod 가 항상 운영 URL 로 구워진다).
  //   ※ 웹 배포(Dockerfile)는 cp .env.prd .env 후 yarn build 라 mode 없이도
  //     동작했다 — 그래서 이 문제가 iOS 빌드에서만 드러났다.
  const env = loadEnv(mode, process.cwd());

  const missing = REQUIRED_ENV.filter((k) => !env[k]);
  if (missing.length) {
    throw new Error(
      `[vite] mode='${mode}' 환경변수 누락: ${missing.join(', ')}\n`
      + `  .env / .env.${mode} 를 확인하세요. 두 파일 모두 gitignore 대상이라\n`
      + `  새로 클론한 머신에는 없습니다(aes.key 등과 같은 취급).\n`
      + `  로컬개발=.env.dev / 배포=.env.prd`
    );
  }

  // 어떤 환경으로 구워졌는지 빌드 로그에 남긴다 — 잘못된 서버로 TestFlight 에
  // 올라가는 사고를 이 한 줄만 보고도 잡을 수 있다.
  console.log(`[vite] mode=${mode} | API=${env.VITE_SERVER_URL} | BATCH=${env.VITE_BATCH_SERVER_URL} | target=${process.env.BUILD_TARGET || 'web'}`);

  return {
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
    adsenseWebOnly(command),
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
  };
});
