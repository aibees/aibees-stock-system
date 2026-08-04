import { toast } from "vue3-toastify";

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