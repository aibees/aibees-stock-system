import { toast } from "vue3-toastify";
// ⚠ 이 CSS import 를 지우지 말 것.
//   vue3-toastify 는 스타일을 자동으로 주입하지 않는다(package.json 에 style 필드도 없다).
//   빠뜨리면 toast DOM 은 만들어지지만 position/z-index 가 하나도 안 먹어서
//   화면 우상단이 아니라 **문서 흐름대로 페이지 하단에 그냥 쌓인다.**
//   toast 를 쓰려면 반드시 이 모듈을 거치므로 여기에 두면 항상 함께 로드된다.
import "vue3-toastify/dist/index.css";

class MariaToast {

    warning(msg) {
        this.common(msg, 'warning');
    }

    error(msg) {
        this.common(msg, 'error');
    }

    info(msg) {
        this.common(msg, 'info');
    }

    success(msg) {
        this.common(msg, 'success');
    }

    common(msg, types) {
        toast(msg, {
            theme: 'colored',
            type: types,
            position: 'top-right',
            pauseOnHover: true,
            autoClose: 2000,
            hideProgressBar: true
        });
    }
}

export default new MariaToast();