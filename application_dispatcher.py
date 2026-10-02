"""Application dispatcher.

Only zero-cost, explicitly configured channels may send automatically.
Paid bids and browser challenges are never silently accepted.
"""
import os, smtplib
from email.message import EmailMessage

def dispatch(lead, proposal):
    if lead.get("paid_bid") is True:
        return {"status":"SKIPPED","reason":"paid_bid"}
    email=lead.get("apply_email")
    if not email:
        return {"status":"NEEDS_CONFIRMATION","reason":"no_free_direct_channel"}
    if os.getenv("AUTO_SEND_EMAIL","0")!="1":
        return {"status":"SHORTLISTED","reason":"email_send_disabled"}
    host=os.getenv("SMTP_HOST"); user=os.getenv("SMTP_USER"); password=os.getenv("SMTP_PASSWORD")
    if not all((host,user,password)):
        return {"status":"SHORTLISTED","reason":"smtp_not_configured"}
    msg=EmailMessage()
    msg["From"]=user; msg["To"]=email
    msg["Subject"]=f"Отклик: {lead.get('title','проект')}"
    msg.set_content(proposal)
    with smtplib.SMTP_SSL(host,int(os.getenv("SMTP_PORT","465")),timeout=30) as s:
        s.login(user,password); s.send_message(msg)
    return {"status":"SUBMITTED","reason":"email_sent"}
