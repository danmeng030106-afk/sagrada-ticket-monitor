import os
import re
import sys
import smtplib
from datetime import datetime
from email.message import EmailMessage
from playwright.sync_api import sync_playwright

BASE = "https://tickets.sagradafamilia.org/en/1-individual/"

PRODUCTS = {
    "Standard": "4375-sagrada-familia",
    "Towers": "4443-sagrada-familia-with-towers",
    "Guided Tour": "4374-sagrada-familia-amb-visita-guiada",
    "Guided Tour + Towers":
        "4779-sagrada-familia-with-guide-and-visit-to-the-towers",
}

DATES = ["2026-12-27", "2026-12-28"]
EMAIL = os.getenv("ALERT_EMAIL", "danmeng030106@gmail.com")


def send_email(findings):
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_APP_PASSWORD"]

    message = EmailMessage()
    message["From"] = user
    message["To"] = EMAIL
    message["Subject"] = "[Sagrada] Potential ticket availability"

    lines = [
        "Potentially selectable ticket times were found.",
        "Please verify availability on the official website.",
        "",
    ]

    for item in findings:
        lines.extend([
            f"Ticket: {item['product']}",
            f"Date: {item['date']}",
            f"Times: {', '.join(item['times'])}",
            f"Official link: {item['url']}",
            "",
        ])

    message.set_content("\n".join(lines))

    with smtplib.SMTP_SSL(
        "smtp.gmail.com", 465, timeout=30
    ) as server:
        server.login(user, password)
        server.send_message(message)


def check_product(browser, name, slug):
    url = BASE + slug
    results = []

    for date in DATES:
        page = browser.new_page(
            viewport={"width": 1400, "height": 900}
        )

        try:
            print(f"Checking {name} {date}", flush=True)

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            heading = page.get_by_text(
                "December 2026", exact=True
            )

            if heading.count() == 0:
                page.get_by_text(
                    "November 2026", exact=True
                ).wait_for(timeout=20000)

                page.get_by_role(
                    "button",
                    name="Move forward to switch to the next month."
                ).click()

            heading.wait_for(timeout=20000)

            # Wait for the calendar to settle.
            page.wait_for_timeout(3000)

            day = int(date[-2:])
            date_id = f"{day:02d}/12/2026"

            cell = page.locator(
                'td.CalendarDay[role="button"]'
            ).filter(
                has=page.locator(
                    f'[data-date-id="{date_id}"]'
                )
            )

            if cell.count() != 1:
                print("CHECK FAILED: date element missing")
                continue

            if cell.get_attribute("aria-disabled") == "true":
                print("Date not selectable")
                continue

            cell.click()
            page.wait_for_timeout(3000)

            buttons = page.locator("button.event")
            times = []

            for i in range(buttons.count()):
                button = buttons.nth(i)

                if button.is_visible() and button.is_enabled():
                    event_date = button.get_attribute(
                        "data-event-id"
                    ) or ""

                    if event_date.startswith(date + "T"):
                        time = event_date[11:16]

                        if re.fullmatch(r"\d{2}:\d{2}", time):
                            times.append(time)

            times = sorted(set(times))

            if times:
                print("POTENTIAL TIMES:", times)
                results.append({
                    "product": name,
                    "date": date,
                    "times": times,
                    "url": url,
                })
            else:
                print("No selectable time buttons detected")

        except Exception as error:
            print(
                "CHECK FAILED:",
                type(error).__name__,
                str(error)[:200]
            )

        finally:
            page.close()

    return results


def main():
    findings = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=os.getenv("HEADLESS", "0") == "1"
        )

        try:
            for name, slug in PRODUCTS.items():
                findings.extend(
                    check_product(browser, name, slug)
                )
        finally:
            browser.close()

    print("\n=== RESULTS ===", flush=True)

    if findings:
        for item in findings:
            print(item, flush=True)

        if os.getenv("SEND_ALERTS", "0") == "1":
            send_email(findings)
            print("Alert email sent.")
        else:
            print("Dry run: email not sent.")
    else:
        print("No potential time slots detected.")

    print("Check finished:", datetime.now().isoformat())


if __name__ == "__main__":
    main()
