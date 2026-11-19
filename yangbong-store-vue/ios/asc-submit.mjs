#!/usr/bin/env node
/**
 * App Store Connect 심사 제출 자동화 (2026-11-19).
 *
 *   업로드(archive.sh --upload) 다음 단계를 API 로 한 번에 한다:
 *     빌드 처리 완료 대기 → 버전(편집 중인 것 재사용/생성) → 출시 방식 → 빌드 연결 → 메타데이터 점검 → 심사 제출
 *
 *   node ios/asc-submit.mjs --check                       점검만(아무것도 바꾸지 않음)
 *   node ios/asc-submit.mjs --build 202611192204 --version 1.2.0
 *   node ios/asc-submit.mjs                               가장 최근 빌드를 제출
 *
 *   옵션
 *     --build <번호>         CFBundleVersion(archive.sh 가 찍는 빌드번호). 없으면 가장 최근 업로드 빌드
 *     --version <x.y.z>      스토어 표시 버전. 없으면 빌드의 버전
 *     --release manual|after 승인 후 출시 방식. 기본 manual(승인돼도 '출시' 버튼을 눌러야 나간다)
 *     --wait <분>            빌드 처리 대기 한도(기본 45분)
 *     --check                쓰기 없이 상태·빠진 메타데이터만 보여 준다
 *
 *   인증: ios/asc.env.local 의 ASC_KEY_ID / ASC_ISSUER_ID (archive.sh 와 같은 파일), 키 파일은 AuthKey_<ID>.p8.
 *   번들 ID: capacitor.config.prod.json 의 appId.
 *   의존성 없음(Node 18+ 내장 fetch·crypto).
 *
 *   API 로 못 하는 것(처음 한 번 웹에서): 앱 개인정보(데이터 수집) 응답, 가격·배포 국가.
 *   스크린샷·설명·키워드·지원 URL·개인정보처리방침 URL·연령 등급·심사 연락처도 비어 있으면 제출이 거절된다 — 점검 결과에 나온다.
 */
import { readFileSync, existsSync } from 'node:fs';
import { createPrivateKey, sign } from 'node:crypto';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const API = 'https://api.appstoreconnect.apple.com';
const EDITABLE = new Set(['PREPARE_FOR_SUBMISSION', 'DEVELOPER_REJECTED', 'REJECTED', 'METADATA_REJECTED', 'INVALID_BINARY']);
const IN_REVIEW = new Set(['WAITING_FOR_REVIEW', 'IN_REVIEW', 'PENDING_APPLE_RELEASE', 'PENDING_DEVELOPER_RELEASE', 'PROCESSING_FOR_APP_STORE', 'READY_FOR_REVIEW']);

/* ── 인자 ── */
const args = process.argv.slice(2);
const opt = (name, fallback = null) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : fallback; };
const CHECK = args.includes('--check');
const BUILD_NO = opt('--build');
let VERSION = opt('--version');
const RELEASE = (opt('--release', 'manual') === 'after') ? 'AFTER_APPROVAL' : 'MANUAL';
const WAIT_MIN = Number(opt('--wait', '45'));

/* ── 출력 ── */
const log = (...a) => console.log(...a);
const step = (s) => log(`\n>>> ${s}`);
const die = (msg) => { console.error(`\n[중단] ${msg}`); process.exit(1); };

/* ── 인증 ── */
function loadEnv() {
  const f = resolve(ROOT, 'ios/asc.env.local');
  const env = {};
  if (existsSync(f)) {
    for (const line of readFileSync(f, 'utf8').split('\n')) {
      const m = line.match(/^\s*(?:export\s+)?([A-Z_]+)\s*=\s*"?([^"#\n]*)"?/);
      if (m) env[m[1]] = m[2].trim();
    }
  }
  const keyId = process.env.ASC_KEY_ID || env.ASC_KEY_ID;
  const issuer = process.env.ASC_ISSUER_ID || env.ASC_ISSUER_ID;
  const keyPath = process.env.ASC_KEY_PATH || env.ASC_KEY_PATH || resolve(ROOT, `AuthKey_${keyId}.p8`);
  if (!keyId || !issuer) die('ASC_KEY_ID / ASC_ISSUER_ID 가 없습니다(ios/asc.env.local).');
  if (!existsSync(keyPath)) die(`키 파일이 없습니다: ${keyPath}`);
  return { keyId, issuer, key: createPrivateKey(readFileSync(keyPath, 'utf8')) };
}
const AUTH = loadEnv();
const b64 = (o) => Buffer.from(typeof o === 'string' ? o : JSON.stringify(o)).toString('base64url');
function token() {
  const now = Math.floor(Date.now() / 1000);
  const head = b64({ alg: 'ES256', kid: AUTH.keyId, typ: 'JWT' });
  const body = b64({ iss: AUTH.issuer, iat: now, exp: now + 15 * 60, aud: 'appstoreconnect-v1' });
  const sig = sign('sha256', Buffer.from(`${head}.${body}`), { key: AUTH.key, dsaEncoding: 'ieee-p1363' }).toString('base64url');
  return `${head}.${body}.${sig}`;
}

/* ── API ── */
async function api(method, path, body) {
  const res = await fetch(API + path, {
    method,
    headers: { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const json = text ? JSON.parse(text) : {};
  if (!res.ok) {
    const err = new Error(`${method} ${path} → ${res.status}`);
    err.status = res.status; err.errors = json.errors || [];
    throw err;
  }
  return json;
}
const get = (p) => api('GET', p);
function explain(e) {
  const lines = [`  ${e.message}`];
  for (const x of e.errors || []) {
    lines.push(`  - ${x.title || x.code}: ${x.detail || ''}`);
    for (const a of x.meta?.associatedErrors ? Object.values(x.meta.associatedErrors).flat() : []) {
      lines.push(`      · ${a.detail || a.title || a.code}`);
    }
  }
  return lines.join('\n');
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ── 1. 앱 ── */
const BUNDLE_ID = JSON.parse(readFileSync(resolve(ROOT, 'capacitor.config.prod.json'), 'utf8')).appId;
step(`앱 찾기 (${BUNDLE_ID})`);
const app = (await get(`/v1/apps?filter[bundleId]=${encodeURIComponent(BUNDLE_ID)}`)).data[0];
if (!app) die(`App Store Connect 에 ${BUNDLE_ID} 앱이 없습니다. 웹에서 새 앱을 먼저 등록하세요.`);
log(`  ${app.attributes.name} (앱 ID ${app.id})`);

/* ── 2. 빌드 처리 완료 대기 ── */
step(`빌드 처리 확인${BUILD_NO ? ` (빌드 ${BUILD_NO})` : ' (가장 최근 빌드)'}`);
const buildQuery = `/v1/builds?filter[app]=${app.id}&include=preReleaseVersion&sort=-uploadedDate&limit=1`
  + (BUILD_NO ? `&filter[version]=${encodeURIComponent(BUILD_NO)}` : '');
const deadline = Date.now() + WAIT_MIN * 60_000;
let build, buildVersion;
for (;;) {
  const r = await get(buildQuery);
  build = r.data[0];
  if (build) {
    buildVersion = r.included?.find((x) => x.type === 'preReleaseVersions')?.attributes?.version;
    const st = build.attributes.processingState;
    log(`  빌드 ${build.attributes.version} (버전 ${buildVersion}) — ${st}`);
    if (st === 'VALID') break;
    if (st === 'FAILED' || st === 'INVALID') die(`빌드 처리가 ${st} 로 끝났습니다. App Store Connect 의 빌드 화면에서 사유를 확인하세요.`);
  } else {
    log('  아직 App Store Connect 에 빌드가 보이지 않습니다.');
  }
  if (CHECK) { if (!build || build.attributes.processingState !== 'VALID') log('  (--check: 기다리지 않고 계속 점검합니다)'); break; }
  if (Date.now() > deadline) die(`${WAIT_MIN}분 안에 빌드 처리가 끝나지 않았습니다. 나중에 같은 명령으로 다시 실행하세요.`);
  await sleep(30_000);
}
VERSION = VERSION || buildVersion;
if (!VERSION) die('버전을 알 수 없습니다(--version 으로 지정하세요).');

/* ── 3. 버전 ── */
step(`스토어 버전 ${VERSION}`);
const versions = (await get(`/v1/apps/${app.id}/appStoreVersions?filter[platform]=IOS&limit=50`)).data;
const stateOf = (v) => v.attributes.appVersionState || v.attributes.appStoreState;
const busy = versions.find((v) => IN_REVIEW.has(stateOf(v)));
if (busy) die(`버전 ${busy.attributes.versionString} 가 이미 ${stateOf(busy)} 상태입니다. 그 심사가 끝나거나 취소된 뒤에 제출할 수 있습니다.`);
let version = versions.find((v) => v.attributes.versionString === VERSION && EDITABLE.has(stateOf(v)))
  || versions.find((v) => EDITABLE.has(stateOf(v)));
if (CHECK) {
  log(version ? `  편집 중인 버전 ${version.attributes.versionString} (${stateOf(version)}) 을 ${VERSION} 로 씁니다`
              : `  편집 중인 버전이 없어 ${VERSION} 을 새로 만듭니다`);
} else if (!version) {
  version = (await api('POST', '/v1/appStoreVersions', { data: {
    type: 'appStoreVersions', attributes: { platform: 'IOS', versionString: VERSION, releaseType: RELEASE },
    relationships: { app: { data: { type: 'apps', id: app.id } } } } })).data;
  log(`  새 버전 ${VERSION} 생성`);
} else {
  const attrs = { releaseType: RELEASE };
  if (version.attributes.versionString !== VERSION) attrs.versionString = VERSION;
  await api('PATCH', `/v1/appStoreVersions/${version.id}`, { data: { type: 'appStoreVersions', id: version.id, attributes: attrs } });
  log(`  버전 ${version.attributes.versionString}${attrs.versionString ? ` → ${VERSION}` : ''} 사용, 출시 방식 ${RELEASE === 'MANUAL' ? '수동' : '승인 즉시'}`);
}

/* ── 4. 빌드 연결 ── */
if (!CHECK && version && build) {
  step('빌드 연결');
  await api('PATCH', `/v1/appStoreVersions/${version.id}/relationships/build`, { data: { type: 'builds', id: build.id } });
  log(`  빌드 ${build.attributes.version} → 버전 ${VERSION}`);
}

/* ── 5. 메타데이터 점검 (읽기만) ── */
step('제출 전 점검');
const problems = [];
const ok = (msg) => log(`  ✓ ${msg}`);
const bad = (msg) => { log(`  ✗ ${msg}`); problems.push(msg); };
if (version) {
  const locs = (await get(`/v1/appStoreVersions/${version.id}/appStoreVersionLocalizations`)).data;
  if (!locs.length) bad('버전 현지화(설명 등)가 없습니다');
  for (const l of locs) {
    const a = l.attributes, tag = `[${a.locale}]`;
    const miss = ['description', 'keywords', 'supportUrl'].filter((k) => !a[k]);
    miss.length ? bad(`${tag} 비어 있음: ${miss.map((k) => ({ description: '설명', keywords: '키워드', supportUrl: '지원 URL' })[k]).join(', ')}`)
                : ok(`${tag} 설명·키워드·지원 URL`);
    const sets = await get(`/v1/appStoreVersionLocalizations/${l.id}/appScreenshotSets?include=appScreenshots&limit=50`);
    const filled = sets.data.filter((s) => (s.relationships?.appScreenshots?.data || []).length > 0);
    filled.length ? ok(`${tag} 스크린샷 ${filled.length}종(${filled.map((s) => s.attributes.screenshotDisplayType.replace('APP_', '')).join(', ')})`)
                  : bad(`${tag} 스크린샷이 없습니다(iPhone 6.9/6.5 인치 필요)`);
  }
  try {
    const rd = (await get(`/v1/appStoreVersions/${version.id}/appStoreReviewDetail`)).data;
    const a = rd?.attributes || {};
    const miss = ['contactFirstName', 'contactLastName', 'contactPhone', 'contactEmail'].filter((k) => !a[k]);
    miss.length ? bad('심사 연락처(이름·전화·이메일)가 비어 있습니다') : ok('심사 연락처');
    if (a.demoAccountRequired && !(a.demoAccountName && a.demoAccountPassword)) bad('데모 계정이 필요하다고 표시됐는데 계정 정보가 없습니다');
  } catch (e) { e.status === 404 ? bad('심사 정보(연락처·데모 계정)가 없습니다') : log(explain(e)); }
} else {
  log('  (버전이 아직 없어 버전 메타데이터는 제출 때 확인됩니다)');
}
const infos = (await get(`/v1/apps/${app.id}/appInfos`)).data;
const info = infos.find((i) => EDITABLE.has(i.attributes.appStoreState || i.attributes.state)) || infos[0];
if (info) {
  const ils = (await get(`/v1/appInfos/${info.id}/appInfoLocalizations`)).data;
  for (const l of ils) {
    l.attributes.privacyPolicyUrl ? ok(`[${l.attributes.locale}] 개인정보처리방침 URL`) : bad(`[${l.attributes.locale}] 개인정보처리방침 URL 이 없습니다`);
  }
  const full = await get(`/v1/appInfos/${info.id}?include=primaryCategory`);
  full.data.relationships?.primaryCategory?.data ? ok('카테고리') : bad('카테고리가 정해지지 않았습니다');
  try {
    const ar = (await get(`/v1/appInfos/${info.id}/ageRatingDeclaration`)).data;
    // 새 앱은 일부 값만 기본으로 채워져 있다 — 설문의 주요 문항이 모두 답해졌는지 본다.
    const KEYS = ['alcoholTobaccoOrDrugUseOrReferences', 'violenceCartoonOrFantasy', 'profanityOrCrudeHumor',
      'sexualContentOrNudity', 'horrorOrFearThemes', 'medicalOrTreatmentInformation', 'violenceRealistic'];
    const unanswered = KEYS.filter((k) => (ar?.attributes || {})[k] == null);
    unanswered.length ? bad(`연령 등급 설문 미완료(${unanswered.length}문항)`) : ok('연령 등급 설문');
  } catch { bad('연령 등급 설문을 확인하지 못했습니다'); }
}
log('  · 앱 개인정보(데이터 수집)·가격·배포 국가는 API 로 확인할 수 없습니다 — 처음 한 번 웹에서 채워 두세요.');

if (CHECK) {
  log(`\n점검만 했습니다(--check). ${problems.length ? `빠진 것 ${problems.length}개를 채우면 제출할 수 있습니다.` : '빠진 것이 없습니다.'}`);
  process.exit(problems.length ? 3 : 0);
}
if (!build || build.attributes.processingState !== 'VALID') die('제출할 빌드가 준비되지 않았습니다.');
if (problems.length) die(`빠진 메타데이터 ${problems.length}개를 App Store Connect 에서 채운 뒤 다시 실행하세요. (빌드 연결까지는 끝났습니다)`);

/* ── 6. 심사 제출 ── */
step('심사 제출');
try {
  const open = (await get(`/v1/reviewSubmissions?filter[app]=${app.id}&filter[platform]=IOS&filter[state]=READY_FOR_REVIEW,UNRESOLVED_ISSUES,WAITING_FOR_REVIEW,IN_REVIEW`)).data;
  if (open.some((s) => ['WAITING_FOR_REVIEW', 'IN_REVIEW'].includes(s.attributes.state))) die('이미 심사 대기 중인 제출이 있습니다.');
  let sub = open.find((s) => s.attributes.state === 'READY_FOR_REVIEW' || s.attributes.state === 'UNRESOLVED_ISSUES');
  if (!sub) {
    sub = (await api('POST', '/v1/reviewSubmissions', { data: { type: 'reviewSubmissions', attributes: { platform: 'IOS' },
      relationships: { app: { data: { type: 'apps', id: app.id } } } } })).data;
  }
  try {
    await api('POST', '/v1/reviewSubmissionItems', { data: { type: 'reviewSubmissionItems', relationships: {
      reviewSubmission: { data: { type: 'reviewSubmissions', id: sub.id } },
      appStoreVersion: { data: { type: 'appStoreVersions', id: version.id } } } } });
  } catch (e) {
    if (e.status !== 409) throw e;   // 이미 들어 있으면 그대로 진행
  }
  await api('PATCH', `/v1/reviewSubmissions/${sub.id}`, { data: { type: 'reviewSubmissions', id: sub.id, attributes: { submitted: true } } });
  log(`  제출 완료 — 버전 ${VERSION}, 빌드 ${build.attributes.version}, 출시 방식 ${RELEASE === 'MANUAL' ? '수동(승인 후 직접 출시)' : '승인 즉시'}`);
} catch (e) {
  die(`심사 제출이 거절됐습니다.\n${explain(e)}`);
}
