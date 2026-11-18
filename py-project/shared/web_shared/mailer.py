"""
메일 발송 (회원가입 인증코드 등).

SMTP 계정은 아래 순서로 찾는다.
  1) DB master_infos  category='SMTP'  key_type = SMTP_USER / SMTP_PASSWORD / SMTP_HOST / SMTP_PORT
  2) smtp.key 파일 (py-stock-batch/spec_keys/smtp.key 와 같은 4줄 형식: 보내는 주소, 비밀번호, 서버, 포트)
     - 이 프로젝트 루트(작업 디렉터리)의 smtp.key
     - 로컬 개발용: ../py-stock-batch/spec_keys/smtp.key
배포 서버에는 1) 또는 2) 중 하나가 있어야 한다. 없으면 send() 가 MailerError 를 던진다.
"""
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr

from app.domains.dao.masterInfoDao import MasterInfosDao

_KEY_FILES = ('smtp.key', os.path.join('..', 'py-stock-batch', 'spec_keys', 'smtp.key'))
_SENDER_NAME = '양봉상회'


class MailerError(Exception):
    pass


def _load_config(session) -> dict:
    rows = {r['key_type']: r['key_value']
            for r in MasterInfosDao().select_master_key_by_category(session, 'SMTP')}
    if rows.get('SMTP_USER') and rows.get('SMTP_PASSWORD') and rows.get('SMTP_HOST'):
        return {'user': rows['SMTP_USER'], 'password': rows['SMTP_PASSWORD'],
                'host': rows['SMTP_HOST'], 'port': int(rows.get('SMTP_PORT') or 465)}

    for path in _KEY_FILES:
        if os.path.exists(path):
            with open(path) as f:
                lines = [ln.strip() for ln in f.readlines()]
            if len(lines) >= 4:
                return {'user': lines[0], 'password': lines[1], 'host': lines[2], 'port': int(lines[3])}
    raise MailerError("SMTP 설정이 없습니다 (master_infos SMTP 또는 smtp.key).")


def send(session, to: str, subject: str, html: str) -> None:
    cfg = _load_config(session)
    msg = MIMEText(html, 'html', 'utf-8')
    msg['From'] = formataddr((_SENDER_NAME, cfg['user']))
    msg['To'] = to
    msg['Subject'] = subject
    try:
        with smtplib.SMTP_SSL(cfg['host'], cfg['port'], context=ssl.create_default_context(), timeout=15) as s:
            s.login(cfg['user'], cfg['password'])
            s.sendmail(cfg['user'], [to], msg.as_string())
    except Exception as e:
        raise MailerError(str(e)) from e
