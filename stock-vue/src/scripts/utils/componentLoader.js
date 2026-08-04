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

    const moduleLoader = modules[componentPath] ?? modulesLowerMap[componentPath.toLowerCase()]?.loader;

    if (!moduleLoader) {
        console.error('[componentLoader] 등록된 컴포넌트 목록:', Object.keys(modules));
        console.error('[componentLoader] 요청 경로:', componentPath);
        throw new Error(`component not Found => ${componentPath}`);
    }

    return moduleLoader;
}