/**
 * v-draggable
 * 레이어 팝업(.popup-panel 등)을 마우스/터치로 드래그하여 이동시키는 커스텀 디렉티브.
 *
 * 사용법:
 *   <div class="popup-panel" v-draggable>          → 내부 .popup-header 를 드래그 핸들로 사용
 *   <div class="popup-panel" v-draggable=".my-handle"> → 지정한 셀렉터를 드래그 핸들로 사용
 *
 * - 버튼/링크/입력 요소를 클릭한 경우는 드래그를 시작하지 않습니다.
 * - 이동은 transform: translate() 로 처리되며, 팝업이 다시 열릴 때(엘리먼트 재생성) 위치는 초기화됩니다.
 */
export default {
    mounted(el, binding) {
        const handleSelector = binding.value || '.popup-header';
        const handle = el.querySelector(handleSelector) || el;

        handle.style.cursor = 'move';
        handle.style.userSelect = 'none';

        el._dragX = 0;
        el._dragY = 0;

        let dragging = false;
        let startX = 0;
        let startY = 0;
        let origX = 0;
        let origY = 0;

        const onPointerMove = (e) => {
            if (!dragging) return;
            const point = e.touches ? e.touches[0] : e;
            const dx = point.clientX - startX;
            const dy = point.clientY - startY;
            el._dragX = origX + dx;
            el._dragY = origY + dy;
            el.style.transform = `translate(${el._dragX}px, ${el._dragY}px)`;
            e.preventDefault();
        };

        const onPointerUp = () => {
            dragging = false;
            handle.style.cursor = 'move';
            document.removeEventListener('mousemove', onPointerMove);
            document.removeEventListener('mouseup', onPointerUp);
            document.removeEventListener('touchmove', onPointerMove);
            document.removeEventListener('touchend', onPointerUp);
        };

        const onPointerDown = (e) => {
            // 버튼/입력 요소 클릭 시에는 드래그 시작 안 함
            if (e.target.closest('button, a, input, textarea, select, label')) return;

            dragging = true;
            const point = e.touches ? e.touches[0] : e;
            startX = point.clientX;
            startY = point.clientY;
            origX = el._dragX;
            origY = el._dragY;
            handle.style.cursor = 'grabbing';

            document.addEventListener('mousemove', onPointerMove);
            document.addEventListener('mouseup', onPointerUp);
            document.addEventListener('touchmove', onPointerMove, { passive: false });
            document.addEventListener('touchend', onPointerUp);
            e.preventDefault();
        };

        handle.addEventListener('mousedown', onPointerDown);
        handle.addEventListener('touchstart', onPointerDown, { passive: false });

        el._draggableCleanup = () => {
            handle.removeEventListener('mousedown', onPointerDown);
            handle.removeEventListener('touchstart', onPointerDown);
            onPointerUp();
        };
    },
    unmounted(el) {
        if (el._draggableCleanup) {
            el._draggableCleanup();
        }
    }
};
