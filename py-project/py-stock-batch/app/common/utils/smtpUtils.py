import smtplib
import ssl
from email.mime.text import MIMEText

class EmailSender:
    def __init__(self):
        self.__name__ = 'EmailSender'
        self.context = ssl.create_default_context()
        self.__settingSender()
    
    def __settingSender(self):
        with open('./smtp.key') as f:
            keyLines = f.readlines()
            self.sender_mail = keyLines[0].strip()
            self.sender_pswd = keyLines[1].strip()
            self.sender_serv = keyLines[2].strip()
            self.sender_port = int(keyLines[3].strip())

    def sendMail(self, subject, body, receipt):
        # create message object
        msg = MIMEText(body, 'html', 'utf-8')
        msg['From'] = self.sender_mail
        msg['To'] = receipt
        msg['Subject'] = subject

        try:
            with smtplib.SMTP_SSL(self.sender_serv, self.sender_port, context=self.context) as sender:
                sender.login(self.sender_mail, self.sender_pswd)
                sender.sendmail(self.sender_mail, receipt, msg.as_string())

            return { 'result' : 'success', 'msg': 'email sent successfully' }
        except Exception as e:
            return { 'result': 'fail', 'msg': e }

emailUtils = EmailSender()