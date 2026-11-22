/**
 * 오픈소스 라이선스 목록(고객지원 > 오픈소스 라이선스).
 * 화면에 실제로 쓰는 글꼴·이미지·라이브러리만 적는다. 새로 넣으면 여기에도 추가한다.
 * 전문은 public/licenses/ 와 각 이미지 폴더의 LICENSE 파일에 있다.
 */
export const LICENSE_TEXTS = {
    'Apache-2.0': '/licenses/APACHE-2.0.txt',
    'OFL-1.1': '/licenses/OFL-1.1-pretendard.txt',
    'MIT-Fluent': '/img/weather/LICENSE-fluentui-emoji.txt',
};

export const LICENSE_GROUPS = [
    {
        title: '글꼴',
        items: [
            { name: 'Pretendard', by: 'Kil Hyung-jin', license: 'SIL Open Font License 1.1', text: 'OFL-1.1', url: 'https://github.com/orioncactus/pretendard' },
        ],
    },
    {
        title: '이모지·아이콘',
        items: [
            { name: 'Noto Emoji (이미지)', by: 'Google LLC', license: 'Apache License 2.0', text: 'Apache-2.0', url: 'https://github.com/googlefonts/noto-emoji', note: '트레이닝·소개 화면의 벌, 꿀, 책 등 이모지 그림' },
            { name: 'Fluent Emoji', by: 'Microsoft Corporation', license: 'MIT License', text: 'MIT-Fluent', url: 'https://github.com/microsoft/fluentui-emoji', note: '홈 화면의 시장 날씨 그림' },
            { name: 'Font Awesome Free', by: 'Fonticons, Inc.', license: '아이콘 CC BY 4.0 · 코드 MIT License', url: 'https://fontawesome.com/license/free' },
        ],
    },
    {
        title: '차트',
        items: [
            { name: 'TradingView Lightweight Charts™', by: 'TradingView, Inc.', license: 'Apache License 2.0', text: 'Apache-2.0', url: 'https://www.tradingview.com/', note: '차트 화면에 TradingView 표시가 함께 보입니다' },
            { name: 'Chart.js', by: 'Chart.js Contributors', license: 'MIT License', url: 'https://github.com/chartjs/Chart.js' },
            { name: 'chartjs-chart-financial · chartjs-plugin-zoom · chartjs-plugin-datalabels', by: 'Chart.js Contributors', license: 'MIT License', url: 'https://github.com/chartjs' },
            { name: 'Hammer.js', by: 'Jorik Tangelder', license: 'MIT License', url: 'https://github.com/hammerjs/hammer.js' },
        ],
    },
    {
        title: '앱 기반',
        items: [
            { name: 'Vue · Vue Router · Pinia', by: 'Evan You and contributors', license: 'MIT License', url: 'https://github.com/vuejs' },
            { name: 'Capacitor', by: 'Ionic', license: 'MIT License', url: 'https://github.com/ionic-team/capacitor' },
            { name: 'Capacitor Firebase Messaging', by: 'Robin Genz', license: 'Apache License 2.0', text: 'Apache-2.0', url: 'https://github.com/capawesome-team/capacitor-firebase' },
            { name: 'Firebase JavaScript SDK', by: 'Google LLC', license: 'Apache License 2.0', text: 'Apache-2.0', url: 'https://github.com/firebase/firebase-js-sdk' },
            { name: 'Capacitor AdMob', by: 'Capacitor Community', license: 'MIT License', url: 'https://github.com/capacitor-community/admob' },
        ],
    },
    {
        title: '그 밖의 라이브러리',
        items: [
            { name: 'axios', by: 'Matt Zabriskie and contributors', license: 'MIT License', url: 'https://github.com/axios/axios' },
            { name: 'Day.js · Luxon', by: 'iamkun · Moment contributors', license: 'MIT License', url: 'https://github.com/iamkun/dayjs' },
            { name: 'marked', by: 'Christopher Jeffrey and contributors', license: 'MIT License', url: 'https://github.com/markedjs/marked' },
            { name: 'DOMPurify', by: 'Cure53 and contributors', license: 'Apache License 2.0 또는 MPL 2.0', text: 'Apache-2.0', url: 'https://github.com/cure53/DOMPurify' },
            { name: 'crypto-js · mitt · vue3-toastify · vuedraggable', by: '각 프로젝트 기여자', license: 'MIT License', url: 'https://www.npmjs.com/' },
        ],
    },
];
