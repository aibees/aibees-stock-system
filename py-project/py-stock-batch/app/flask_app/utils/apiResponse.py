from flask import Response
import json


class ApiResponse:
    @staticmethod
    def success(data=None, message='OK'):
        response_body = {
            'success': True,
            'data': data,
            'message': message
        }
        return Response(
            json.dumps(response_body, ensure_ascii=False),
            status=200,
            content_type='application/json; charset=utf-8'
        )

    @staticmethod
    def error(message='Something went wrong', status=400):
        response_body = {
            'success': False,
            'data': None,
            'message': message
        }
        return Response(
            json.dumps(response_body, ensure_ascii=False),
            status=status,
            content_type='application/json; charset=utf-8'
        )
