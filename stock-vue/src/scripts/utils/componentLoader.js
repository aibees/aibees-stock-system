const modules = import.meta.glob('/src/components/**/*.vue');

// 대소문자 구분 없이 매칭하는 맵 (Docker/Linux 환경 대응)
const modulesLowerMap = Object.fromEntries(
    Object.entries(modules).map(([k, v]) => [k.toLowerCase(), { key: k, loader: v }])
);

export const loadComponent = (routeData) => {
    let componentPath;
    if (routeData.menu_component.endsWith('View')) {
        componentPath = `/src/components/${routeData.menu_code}/${routeData.menu_component}.vue`
    } else if (routeData.menu_parents == 'root') {
        componentPath = `/src/components/${routeData.menu_component}.vue`;
    } else {
        componentPath = `/src/components/${routeData.menu_parents}/${routeData.menu_component}.vue`;
    }

    let moduleLoader = modules[componentPath] ?? modulesLowerMap[componentPath.toLowerCase()]?.loader;

    // 폴백: 메뉴 부모(menu_parents)와 파일이 있는 폴더가 어긋난 경우.
    //   위 규칙은 "폴더 = 메뉴 부모" 라는 관례에 의존한다. 그런데 메뉴를 다른 중분류로
    //   옮기면(예: 개별차트를 차트메뉴 → 주식정보) DB 행만 바뀌고 파일은 그대로라 경로가
    //   빗나간다. 더 위험한 건 여기서 throw 하면 router.js 의 try/catch 가 **모든 메뉴
    //   라우트를 비워버린다**는 점이다 — 행 하나의 불일치가 앱 전체 메뉴를 죽인다.
    //   그래서 파일명(menu_component)이 components 아래에서 **정확히 하나**일 때만 쓴다.
    //   여러 개면 어느 것인지 알 수 없으므로 폴백하지 않고 아래에서 기존처럼 실패시킨다.
    //   DB 변경과 프런트 배포 순서를 맞출 필요도 없어진다(양쪽 상태 모두 해석됨).
    if (!moduleLoader) {
        const suffix = `/${routeData.menu_component}.vue`.toLowerCase();
        const hits = Object.entries(modules).filter(([k]) => k.toLowerCase().endsWith(suffix));
        if (hits.length === 1) {
            console.warn(`[componentLoader] ${componentPath} 없음 → ${hits[0][0]} 로 대체 ` +
                `(menu_parents=${routeData.menu_parents} 와 파일 위치가 다름)`);
            moduleLoader = hits[0][1];
        }
    }

    if (!moduleLoader) {
        console.error('[componentLoader] 등록된 컴포넌트 목록:', Object.keys(modules));
        console.error('[componentLoader] 요청 경로:', componentPath);
        throw new Error(`component not Found => ${componentPath}`);
    }

    return moduleLoader;
}