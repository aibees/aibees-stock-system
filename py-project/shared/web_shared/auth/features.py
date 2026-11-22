"""
서버마다 더하는 기능 플래그(만드는 쪽이 넣는다). 2026-11-22.

role_feature 에 적힌 기능(RoleMenuDao.select_features_for_user) 말고, 서버가 사용자 상태를 보고 잠깐 더해 주는 기능이 있다.
예) 양봉상회: 꿀로 산 프리미엄 하루 이용권을 쓰는 동안 RECO_ADVANCED.
각 서버가 앱을 만들 때 register_feature_provider 로 함수를 넣는다. 넣지 않으면(비밀상회) 아무것도 더하지 않는다.
"""
_providers = []


def register_feature_provider(fn) -> None:
    """fn(session, user_id) -> list[str]. 예외는 삼키고 빈 목록으로 본다."""
    if fn not in _providers:
        _providers.append(fn)


def with_extra_features(session, user_id, features) -> list:
    """role_feature 기능 + 서버가 더하는 기능(중복 제거, 정렬)."""
    extra = []
    for fn in _providers:
        try:
            extra.extend(fn(session, user_id) or [])
        except Exception:
            continue
    return sorted(set(features or []) | set(extra))
