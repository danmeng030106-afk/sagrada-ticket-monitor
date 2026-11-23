import json
import os
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from urllib.request import Request, urlopen

URL = 'https://www.sagradawatcher.com/availability.json'
SHOP = 'https://tickets.sagradafamilia.org/en/1-individual/4375-sagrada-familia'
DATES = ('2026-12-27', '2026-12-28')

def get_data():
    req = Request(URL, headers={'User-Agent': 'PersonalTicketMonitor/1.0 (date-level checking)'})
    with urlopen(req, timeout=25) as resp:
        return json.load(resp)

def extract_general_sale(data):
    """Fail closed if schema cannot be interpreted. Never infer stock from history."""
    raw = data.get('general_sale_dates')
    if not isinstance(raw, list):
        raise ValueError('general_sale_dates missing or not a list; inspect JSON schema')
    dates = set()
    for entry in raw:
        if isinstance(entry, str):
            dates.add(entry[:10])
        elif isinstance(entry, dict):
            date = entry.get('date') or entry.get('visit_date')
            if isinstance(date, str):
                dates.add(date[:10])
    return dates

def send_email(subject, body):
    sender = os.environ['SMTP_USER']
    password = os.environ['SMTP_APP_PASSWORD']
    recipient = os.environ['ALERT_EMAIL']
    msg = EmailMessage()
    msg['From'], msg['To'], msg['Subject'] = sender, recipient, subject
    msg.set_content(body)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=25) as server:
        server.login(sender, password)
        server.send_message(msg)

def main():
    if os.environ.get('TEST_EMAIL') == '1':
        send_email('[TEST] Sagrada monitor', 'Test email succeeded. No ticket availability was checked.')
        print('Test email sent')
        return
    data = get_data()
    print('Data generated at:', data.get('generated_at', 'unknown'))
    sale = extract_general_sale(data)
    hits = [d for d in DATES if d in sale]
    print('General-sale candidate dates:', hits)
    if not hits:
        print('No date-level general-sale signal; no email.')
        return
    # Repeated alerts are intentional: no cross-run state, so each run remains independent.
    send_email('[CHECK NOW] Sagrada Familia possible availability',
               'Date-level general-sale signal for: ' + ', '.join(hits) + '\n\n'
               'IMPORTANT: This does NOT confirm 4 tickets in the same time slot. '
               'Verify immediately on the official site:\n' + SHOP + '\n\n'
               'Source: ' + URL + '\nCredit: Sagrada Watcher (sagradawatcher.com), CC BY 4.0.')
    print('Candidate alert sent')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Monitoring failed:', repr(exc), file=sys.stderr)
        raise
