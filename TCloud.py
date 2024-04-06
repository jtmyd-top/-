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
#    sender_email_password : 发送通知邮箱密码
#    默认域名ssl证书小于60天自动使用outlook邮箱发送邮件
#    search_key:输入需要查询的域名进行筛选，可选

# 获取环境变量中的腾讯云API密钥
secret_id = os.environ.get('secret_id')
secret_key = os.environ.get('secret_key')
sender_email = os.environ.get('sender_email')
receiver_email = os.environ.get('receiver_email')
password = os.environ.get('receiver_email_password')
search_key = os.environ.get('search_key', '')  
    # 从环境变量获取search_key，如果没有设置则默认为空字符串
    
def calculate_countdown(cert_end_time):
    """
    计算证书剩余天数
    """
    end_time = datetime.strptime(cert_end_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    current_time = datetime.now(timezone.utc)
    time_diff = end_time - current_time
    return time_diff.days

def send_email(html_content):
    """
    发送邮件通知
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

def list_certificates(offset=0, limit=200):
    try:
        cred = credential.Credential(secret_id, secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "ssl.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client = ssl_client.SslClient(cred, "ap-guangzhou", client_profile)
        req = models.DescribeCertificatesRequest()
        
        # 设置请求参数，包括search_key
        params = {
            "Offset": offset,
            "Limit": limit
        }
        if search_key:
            params["SearchKey"] = search_key
        req.from_json_string(json.dumps(params))
        
        resp = client.DescribeCertificates(req)
        certificates = json.loads(resp.to_json_string())        
        if 'Certificates' in certificates and certificates['Certificates']:
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
        else:
            print("没有找到任何证书信息。")
        
    except TencentCloudSDKException as e:
        logging.error("获取证书列表失败：" + str(e))
    except Exception as e:
        logging.error("未知错误：" + str(e))

def generate_html_table(certificates):
    """
    生成HTML格式的表格
    """
    html_table = "<table style='border: 1px solid black; border-collapse: collapse;'>"
    html_table += "<tr><th style='border: 1px solid black; padding: 5px;'>域名</th>"
    html_table += "<th style='border: 1px solid black; padding: 5px;'>证书到期时间</th>"
    html_table += "<th style='border: 1px solid black; padding: 5px;'>倒计时</th></tr>"
    
    for domain, end_time, countdown in certificates:
        html_table += f"<tr><td style='border: 1px solid black; padding: 5px;'>{domain}</td>"
        html_table += f"<td style='border: 1px solid black; padding: 5px;'>{end_time}</td>"
        html_table += f"<td style='border: 1px solid black; padding: 5px;'>{countdown}</td></tr>"
    
    html_table += "</table>"
    return html_table

# 执行获取证书列表并发送邮件的函数
list_certificates()
