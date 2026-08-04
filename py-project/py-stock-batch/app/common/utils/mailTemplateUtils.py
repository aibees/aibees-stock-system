from app.common.utils.dotDict import DotDict

class MailTemplateUtils:

    def title(self, data, bold=3):
        return f'''<h{bold}>{data}</h{bold}><hr />'''

    def table(self, thead, tbody):
        return f'''<table border="2" cellspacing="0" style="width:70%;">{thead}{tbody}</table>'''

    def thead(self, data):
        return f'''<thead>{data}</thead>'''

    def th(self, data, align='center'):
        return f'''<th style="padding: 6px; text-align: {align};">{data}</th>'''

    def tbody(self, trs):
        data = ''.join(trs)
        return f'''<tbody>{data}</tbody>'''
    
    def tr(self, tds):
        data = ''.join(tds)
        return f'''<tr>{data}</tr>'''

    def td(self, data, align='center'):
        return f'''<td style="padding: 8px; text-align: {align};">{data}</td>'''


    def indicator_mail(self, param):
        data = DotDict(param)

        return f'''
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="width:100%; background:#ffffff; margin:0; padding:0;">
            <tr>
                <td align="center" style="padding:12px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="450" style="width:450px; border-collapse:collapse; font-family:Arial, Helvetica, 'Noto Sans KR', sans-serif; color:#111827;">
                        <tr>
                            <td style="padding:12px 10px; border:1px solid #e5e7eb; border-bottom:none; background:#f9fafb;">
                                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
                                    <tr>
                                        <td style="font-weight:700; font-size:16px; color:#111827;">{data.coin}</td>
                                        <td align="right" style="font-size:12px; color:#6b7280;">2025-10-09 16:00 (KST)</td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        <tr>
                            <td style="border:1px solid #e5e7eb; border-top:none; padding:10px;">
                                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; font-size:13px;">
                                    <tr>
                                        <td style="padding:4px 0; color:#6b7280;">Open</td>
                                        <td align="right" style="padding:4px 0; font-weight:700;">86.8974</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:4px 0; color:#6b7280;">High</td>
                                        <td align="right" style="padding:4px 0; font-weight:700;">87.0124</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:4px 0; color:#6b7280;">Low</td>
                                        <td align="right" style="padding:4px 0; font-weight:700;">86.4681</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:4px 0; color:#6b7280;">Volume</td>
                                        <td align="right" style="padding:4px 0; font-weight:700;">1,085.00</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:6px 0; color:#111827; border-top:1px solid #f3f4f6;">Close</td>
                                        <td align="right" style="padding:6px 0; font-weight:800; color:#111827;">86.8038</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:4px 0; color:#111827;">MACD / Signal</td>
                                        <td align="right" style="padding:4px 0; font-weight:800;">0.3098 / -0.0255</td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

            <!-- Buy section title -->
            <tr>
              <td style="padding:10px 10px 0 10px; font-size:14px; font-weight:700; color:#111827;">📈 매수 조건</td>
            </tr>
            <tr>
              <td style="padding:0 10px 10px 10px; font-size:12px; color:#374151;">가중 0.4·MACD + 0.3·BB + 0.3·KD</td>
            </tr>
            <!-- Buy table -->
            <tr>
              <td style="border:1px solid #e5e7eb; padding:0;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse; font-size:12px;">
                  <thead>
                    <tr>
                      <th align="left" style="padding:6px; background:#f9fafb; border-bottom:1px solid #e5e7eb;">구분</th>
                      <th align="left" style="padding:6px; background:#f9fafb; border-bottom:1px solid #e5e7eb;">지표</th>
                      <th align="left" style="padding:6px; background:#f9fafb; border-bottom:1px solid #e5e7eb;">현재 값</th>
                      <th align="left" style="padding:6px; background:#f9fafb; border-bottom:1px solid #e5e7eb;">기준 / 임계치</th>
                      <th align="right" style="padding:6px; background:#f9fafb; border-bottom:1px solid #e5e7eb;">충족률</th>
                      <th align="center" style="padding:6px; background:#f9fafb; border-bottom:1px solid #e5e7eb;">충족</th>
                      <th align="left" style="padding:6px; background:#f9fafb; border-bottom:1px solid #e5e7eb;">설명</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">추세 필터</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">MACD</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">MACD=0.3098 / Signal=-0.0255</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">MACD &gt; Signal</td>
                      <td align="right" style="padding:6px; border-bottom:1px solid #e5e7eb;">100.00%</td>
                      <td align="center" style="padding:6px; border-bottom:1px solid #e5e7eb; font-weight:700; color:#16a34a;">✅</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">상승 추세 구간에서만 진입</td>
                    </tr>
                    <tr>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">가격 조건</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">Bollinger</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">PrevClose=86.0463 / Lower=82.8470 / Close=86.8038</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">전일 Close &lt; Lower &amp; 금일 Close &gt; Lower</td>
                      <td align="right" style="padding:6px; border-bottom:1px solid #e5e7eb;">50.00%</td>
                      <td align="center" style="padding:6px; border-bottom:1px solid #e5e7eb; font-weight:700; color:#dc2626;">❌</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">하단 밴드 이탈 후 재진입</td>
                    </tr>
                    <tr>
                      <td style="padding:6px;">모멘텀</td>
                      <td style="padding:6px;">Fast K/D</td>
                      <td style="padding:6px;">%K=94.3461 / %D=88.2015</td>
                      <td style="padding:6px;">%K &gt; %D &amp; %K &lt; 30</td>
                      <td align="right" style="padding:6px;">50.00%</td>
                      <td align="center" style="padding:6px; font-weight:700; color:#dc2626;">❌</td>
                      <td style="padding:6px;">골든크로스 &amp; 과매도 반등</td>
                    </tr>
                    <tr>
                      <td colspan="4" align="center" style="padding:8px; background:#eef6ff; font-weight:700;">매수 조건 종합</td>
                      <td align="right" style="padding:8px; font-weight:700;">70.00%</td>
                      <td align="center" style="padding:8px; font-weight:700; color:#dc2626;">❌</td>
                      <td style="padding:8px;">가중 평균(0.4·MACD + 0.3·BB + 0.3·KD)</td>
                    </tr>
                  </tbody>
                </table>
              </td>
            </tr>

            <!-- Sell section title -->
            <tr>
              <td style="padding:14px 10px 0 10px; font-size:14px; font-weight:700; color:#111827;">📉 청산 조건</td>
            </tr>
            <tr>
              <td style="padding:0 10px 10px 10px; font-size:12px; color:#374151;">가중 0.4·BB + 0.3·KD + 0.3·MACD</td>
            </tr>
            <!-- Sell table -->
            <tr>
              <td style="border:1px solid #e5e7eb; padding:0;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse; font-size:12px;">
                  <thead>
                    <tr>
                      <th align="left" style="padding:6px; background:#f3f4f6; border-bottom:1px solid #e5e7eb;">구분</th>
                      <th align="left" style="padding:6px; background:#f3f4f6; border-bottom:1px solid #e5e7eb;">지표</th>
                      <th align="left" style="padding:6px; background:#f3f4f6; border-bottom:1px solid #e5e7eb;">현재 값</th>
                      <th align="left" style="padding:6px; background:#f3f4f6; border-bottom:1px solid #e5e7eb;">기준 / 임계치</th>
                      <th align="right" style="padding:6px; background:#f3f4f6; border-bottom:1px solid #e5e7eb;">충족률</th>
                      <th align="center" style="padding:6px; background:#f3f4f6; border-bottom:1px solid #e5e7eb;">충족</th>
                      <th align="left" style="padding:6px; background:#f3f4f6; border-bottom:1px solid #e5e7eb;">설명</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">가격 조건</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">Bollinger</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">Close=86.8038 / Upper=86.5401</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">Close ≥ Upper or 상단→재진입</td>
                      <td align="right" style="padding:6px; border-bottom:1px solid #e5e7eb;">7.14%</td>
                      <td align="center" style="padding:6px; border-bottom:1px solid #e5e7eb; font-weight:700; color:#16a34a;">✅</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">단기 과열 구간</td>
                    </tr>
                    <tr>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">모멘텀 약화</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">Fast K/D</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">%K=94.3461 / %D=88.2015</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">%K &lt; %D &amp; %K &gt; 70</td>
                      <td align="right" style="padding:6px; border-bottom:1px solid #e5e7eb;">40.58%</td>
                      <td align="center" style="padding:6px; border-bottom:1px solid #e5e7eb; font-weight:700; color:#dc2626;">❌</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">데드크로스 &amp; 과매수권</td>
                    </tr>
                    <tr>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">추세 약화</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">MACD</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">MACD=0.3098 / Signal=-0.0255</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">MACD &lt; Signal</td>
                      <td align="right" style="padding:6px; border-bottom:1px solid #e5e7eb;">0.00%</td>
                      <td align="center" style="padding:6px; border-bottom:1px solid #e5e7eb; font-weight:700; color:#dc2626;">❌</td>
                      <td style="padding:6px; border-bottom:1px solid #e5e7eb;">상승 추세 둔화</td>
                    </tr>
                    <tr>
                      <td colspan="4" align="center" style="padding:8px; background:#fff3f3; font-weight:700;">청산 조건 종합</td>
                      <td align="right" style="padding:8px; font-weight:700;">15.03%</td>
                      <td align="center" style="padding:8px; font-weight:700; color:#16a34a;">✅</td>
                      <td style="padding:8px;">가중 평균(0.4·BB + 0.3·KD + 0.3·MACD)</td>
                    </tr>
                  </tbody>
                </table>
              </td>
            </tr>

            <!-- Footer / CTA (이메일에서는 버튼 스타일만) -->
            <tr>
              <td style="padding:14px 0 6px 0;"></td>
            </tr>
            <tr>
              <td>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
                  <tr>
                    <td align="center" width="50%" style="padding-right:6px;">
                      <a href="#" style="display:inline-block; width:100%; text-align:center; background:#16a34a; color:#ffffff; text-decoration:none; padding:12px 8px; border-radius:8px; font-weight:800; font-size:14px;">매수 후보 저장</a>
                    </td>
                    <td align="center" width="50%" style="padding-left:6px;">
                      <a href="#" style="display:inline-block; width:100%; text-align:center; background:#ef4444; color:#ffffff; text-decoration:none; padding:12px 8px; border-radius:8px; font-weight:800; font-size:14px;">청산 후보 저장</a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding:10px; font-size:11px; color:#6b7280; text-align:center;">
                © 2025 Report • KST 기준
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
        '''

mailUtils = MailTemplateUtils()


