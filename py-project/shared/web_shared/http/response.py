from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from uuid import UUID

from flask import Response
import simplejson as json


def _json_default(o):
    """simplejson 이 모르는 타입의 직렬화 규칙.

    모델 to_dict() 가 DateTime 컬럼을 그대로 반환하는 곳이 많아
    (masterStock.created_date 등 8개 모델) 값이 NULL 이 아닌 행이 결과에
    섞이는 순간 "Object of type datetime is not JSON serializable" 로 죽었다.
    값이 있냐 없냐에 따라 되다 안 되다 해서 원인 파악이 오래 걸린다.

    모델마다 isoformat() 을 붙이는 대신 **응답 계층 한 곳**에서 처리한다.
      · 새 모델이 늘어도 자동으로 커버된다(빠뜨릴 여지가 없다)
      · to_dict() 는 파이썬 타입 그대로 유지 → 배치·worker 등
        API 밖에서 datetime 을 기대하는 호출부가 깨지지 않는다

    ※ Decimal 은 여기서 다루지 않는다. dumps(use_decimal=True) 가
      숫자 리터럴로(문자열 아님) 처리하므로 그쪽이 정확하다.
    """
    if isinstance(o, (datetime, date, time)):
        return o.isoformat()
    if isinstance(o, timedelta):
        return o.total_seconds()
    if isinstance(o, Decimal):          # use_decimal=False 로 호출된 경우 대비
        return float(o)
    if isinstance(o, Enum):
        return o.value
    if isinstance(o, UUID):
        return str(o)
    if isinstance(o, (bytes, bytearray)):
        return o.decode("utf-8", errors="replace")
    if isinstance(o, set):
        return list(o)
    raise TypeError(f"JSON 직렬화 불가 타입: {type(o).__name__}")


def _dumps(body, **kw):
    """응답 본문 직렬화 단일 진입점."""
    kw.setdefault("ensure_ascii", False)
    kw.setdefault("default", _json_default)
    return json.dumps(body, **kw)


class ApiResponse:

    @staticmethod
    def success(data=None, extra=None):
        """
        [수정] 성공 응답 포맷을 프론트엔드 명세에 맞게 통일
        - 기존: { "success": true, "data": ..., "message": "OK" }
        - 변경: { "success": true, "data": ... }
          → 프론트엔드 interceptor가 data.success 만 체크하며,
            불필요한 message 필드를 제거해 명세와 완전히 일치시킴
        - extra: 페이지네이션 정보(totalPages, totalElements, page, size) 등
          최상위 레벨에 추가할 필드가 있을 때 사용
        """
        response_body = {
            'success': True,
            'data': data
        }
        if extra:
            response_body.update(extra)
        return Response(
            _dumps(response_body, use_decimal=True),
            status=200,
            content_type='application/json; charset=utf-8'
        )

    @staticmethod
    def error(message='Something went wrong', status=400):
        """
        [수정] 에러 응답 포맷을 프론트엔드 명세에 맞게 변경
        - 기존: { "success": false, "data": null, "message": "에러 메시지" }
        - 변경: { "success": false, "error": { "message": "에러 메시지" } }
          → 프론트엔드 interceptor가 data.error.message 를 기준으로
            에러 메시지를 파싱하므로, 이 구조를 반드시 지켜야 함
        - status 파라미터로 HTTP 상태코드를 외부에서 지정 가능
          (인증 실패: 401, 일반 클라이언트 오류: 400 등)
        """
        response_body = {
            'success': False,
            'error': {
                'message': message
            }
        }
        return Response(
            _dumps(response_body),
            status=status,
            content_type='application/json; charset=utf-8'
        )

    @staticmethod
    def unauthorized(message='인증이 필요합니다.'):
        """
        [신규] 인증 실패 전용 응답 헬퍼 (HTTP 401)
        - 명세 요구사항: 토큰 없음·만료·서명 불일치 등 모든 인증 실패는
          반드시 401을 반환해야 함 (403 사용 금지)
        - 프론트엔드 axios interceptor가 response.status === 401 을 감지해
          자동으로 로컬 세션을 초기화하고 로그인 페이지로 이동시킴
        - 내부적으로 error()를 재사용해 포맷 일관성 유지
        """
        return ApiResponse.error(message=message, status=401)

    @staticmethod
    def reset_required(message='비밀번호 재설정이 필요한 계정입니다.'):
        """
        [신규] 비밀번호 재설정 대상 계정 응답 헬퍼 (HTTP 200)
        - user_detail.reset_flag == 'Y' 인 사용자가 로그인을 시도할 때 반환
        - 인증 자체는 성공했으나 추가 액션(비밀번호 재설정)이 필요한 상태이므로
          에러가 아닌 success: false + code: RESET_REQUIRED 형태로 구분
        - 프론트엔드는 data.error.code === 'RESET_REQUIRED' 를 감지해
          비밀번호 재설정 페이지로 유도함
        """
        response_body = {
            'success': False,
            'error': {
                'code': 'RESET_REQUIRED',
                'message': message
            }
        }
        return Response(
            _dumps(response_body),
            status=200,
            content_type='application/json; charset=utf-8'
        )
