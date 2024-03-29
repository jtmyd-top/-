import json
import os
import smtplib
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ssl.v20191205 import ssl_client, models
from tabulate import tabulate

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


#获取青龙面板环境变量
#    secret_id ：腾讯云API  ID
#    secret_key：腾讯云API密钥  key
#    sender_email ：发送通知邮箱账号
#    receiver_email : 接收邮件的邮箱账号
#   sender_email_password : 发送通知邮箱密码
#默认域名ssl证书小于60天自动使用outlook邮箱发送邮件


secret_id = os.environ.get('secret_id')
secret_key = os.environ.get('secret_key')
sender_email = os.environ.get('sender_email')
receiver_email = os.environ.get('receiver_email')
password = os.environ.get('sender_email_password')

def calculate_countdown(cert_end_time):
    """
    计算证书剩余天数

    Args:
        cert_end_time (str): 证书到期时间字符串，格式为 "%Y-%m-%d %H:%M:%S"

    Returns:
        int: 证书剩余天数
    """
    end_time = datetime.strptime(cert_end_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    current_time = datetime.now(timezone.utc)
    time_diff = end_time - current_time
    return time_diff.days

def send_email(html_content):
    """
    发送邮件通知

    Args:
        html_content (str): HTML内容
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = "以下证书即将到期"
        msg.attach(MIMEText(html_content, 'html'))
        with smtplib.SMTP('smtp.office365.com', 587) as smtp:
            smtp.starttls()
            smtp.login(sender_email, password)
            smtp.send_message(msg)
        logging.info("邮件已发送。")
    except Exception as e:
        logging.error("发送邮件失败：" + str(e))

def list_certificates():
    try:
        cred = credential.Credential(secret_id, secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "ssl.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client = ssl_client.SslClient(cred, "ap-guangzhou", client_profile)
        req = models.DescribeCertificatesRequest()
        resp = client.DescribeCertificates(req)
        certificates = json.loads(resp.to_json_string())

        table_data = []
        for certificate in certificates['Certificates']:
            cert_end_time = certificate['CertEndTime']
            countdown = calculate_countdown(cert_end_time)
            table_data.append([certificate['Domain'], cert_end_time, f"{countdown}天"])

        headers = ["域名", "证书到期时间", "倒计时"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

        if any(int(certificate[2].replace('天', '')) <= 60 for certificate in table_data):
            html_table = generate_html_table(table_data)
            send_email(html_table)
        else:
            logging.info("没有证书在60天内到期，未发送邮件。")

    except TencentCloudSDKException as e:
        logging.error("获取证书列表失败：" + str(e))
    except Exception as e:
        logging.error("未知错误：" + str(e))

def generate_html_table(certificates):
    html_table = """
    <table style='border: 1px solid black; border-collapse: collapse;'>
        <tr>
            <th style='border: 1px solid black; padding: 5px;'>域名</th>
            <th style='border: 1px solid black; padding: 5px;'>证书到期时间</th>
            <th style='border: 1px solid black; padding: 5px;'>倒计时</th>
        </tr>
    """
    for domain, end_time, countdown in certificates:
        countdown_days = int(countdown.replace('天', ''))
        row_color = ""
        if countdown_days <= 30:
            row_color = "style='background-color: #ffcccc;'"  # 红色
        elif countdown_days <= 60:
            row_color = "style='background-color: #ffffcc;'"  # 黄色
        
        html_table += f"""
        <tr {row_color}>
            <td style='border: 1px solid black; padding: 5px;'>{domain}</td>
            <td style='border: 1px solid black; padding: 5px;'>{end_time}</td>
            <td style='border: 1px solid black; padding: 5px;'>{countdown}天</td>
        </tr>
        """

    html_table += "</table>"
    return html_table

# 获取证书列表并发送邮件
list_certificates()
