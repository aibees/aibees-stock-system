"""
app/exceptions.py — 애플리케이션 공통 커스텀 예외 정의

이 파일을 단일 출처(single source of truth)로 사용해야 합니다.
authService, router 등 여러 레이어에서 같은 예외 클래스를 공유할 때
임포트 경로가 달라지면 Python이 서로 다른 클래스 객체를 만들어
except 블록이 매칭되지 않는 문제가 발생할 수 있습니다.
예외 클래스는 반드시 이 파일에서만 정의하고 여기서만 임포트하세요.
"""


class ResetRequiredException(Exception):
    """
    user_detail.reset_flag == 'Y' 인 계정이 로그인을 시도할 때 발생.
    라우터에서 별도로 catch해 RESET_REQUIRED 응답을 반환함.
    """
    pass
