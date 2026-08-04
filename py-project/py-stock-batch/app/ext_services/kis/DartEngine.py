
import OpenDartReader as dart
import json

class DartEngine:
    def __init__(self, key_path: str = 'dart.key'):
        # 1. 파일에서 설정값 읽어오기
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                keys = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"{key_path} 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
        except json.JSONDecodeError:
            raise ValueError(f"{key_path} 파일의 JSON 형식이 올바르지 않습니다.")

        self.dart = dart(keys.get('key'))


