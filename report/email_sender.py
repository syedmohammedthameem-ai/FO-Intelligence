import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from config import GMAIL_USER, GMAIL_APP_PASSWORD, REPORT_RECIPIENT

logger = logging.getLogger(__name__)


def send_report_email(pdf_path: str, nifty_data: dict, news_sentiment: dict) -> bool:
    """
    Send the daily PDF report via Gmail SMTP.
    Includes a rich HTML summary in the email body.
    """
    today = datetime.now().strftime("%d %B %Y")
    spot = nifty_data.get("spot", 0)
    trend = nifty_data.get("trend", "N/A")
    pcr = nifty_data.get("pcr", 0)
    strategy = nifty_data.get("suggested_strategy", {}).get("name", "N/A")
    sentiment = news_sentiment.get("overall", "NEUTRAL")

    sentiment_color = "#00C853" if "BULL" in sentiment else ("#FF1744" if "BEAR" in sentiment else "#FFD600")
    trend_color = "#00C853" if "BULL" in trend else ("#FF1744" if "BEAR" in trend else "#FFD600")

    html = f"""
    <html><body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
    <div style="max-width: 600px; margin: auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

      <div style="background: #0D47A1; padding: 20px; text-align: center;">
        <h2 style="color: white; margin: 0;">F&amp;O Intelligence Report</h2>
        <p style="color: #90CAF9; margin: 4px 0;">{today}</p>
      </div>

      <div style="padding: 20px;">
        <h3 style="color: #0D47A1; border-bottom: 2px solid #E3F2FD; padding-bottom: 8px;">Quick Snapshot</h3>
        <table style="width: 100%; border-collapse: collapse;">
          <tr style="background: #E3F2FD;">
            <td style="padding: 8px; font-weight: bold;">NIFTY Spot</td>
            <td style="padding: 8px;">{spot:,.2f}</td>
          </tr>
          <tr>
            <td style="padding: 8px; font-weight: bold;">Trend</td>
            <td style="padding: 8px; color: {trend_color}; font-weight: bold;">{trend}</td>
          </tr>
          <tr style="background: #E3F2FD;">
            <td style="padding: 8px; font-weight: bold;">PCR</td>
            <td style="padding: 8px;">{pcr:.3f}</td>
          </tr>
          <tr>
            <td style="padding: 8px; font-weight: bold;">IV Rank</td>
            <td style="padding: 8px;">{nifty_data.get('iv_rank', 0):.1f}%</td>
          </tr>
          <tr style="background: #E3F2FD;">
            <td style="padding: 8px; font-weight: bold;">Max Pain</td>
            <td style="padding: 8px;">{nifty_data.get('max_pain', 0):,.0f}</td>
          </tr>
          <tr>
            <td style="padding: 8px; font-weight: bold;">Suggested Strategy</td>
            <td style="padding: 8px; font-weight: bold; color: #0D47A1;">{strategy}</td>
          </tr>
          <tr style="background: #E3F2FD;">
            <td style="padding: 8px; font-weight: bold;">News Sentiment</td>
            <td style="padding: 8px; color: {sentiment_color}; font-weight: bold;">{sentiment}</td>
          </tr>
        </table>

        <p style="margin-top: 20px; color: #666; font-size: 13px;">
          Full analysis including Greeks, OI levels, short-term setups, long-term picks,
          and macro data is attached as a PDF.
        </p>

        <div style="background: #FFF3E0; border-left: 4px solid #FF9800; padding: 12px; border-radius: 4px; margin-top: 16px;">
          <strong>Disclaimer:</strong> For educational purposes only. Not financial advice.
          All investments carry risk.
        </div>
      </div>
    </div>
    </body></html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = GMAIL_USER
        msg["To"] = REPORT_RECIPIENT
        msg["Subject"] = f"F&O Intelligence Report — {today} | NIFTY {spot:,.0f} | {trend}"

        msg.attach(MIMEText(html, "html"))

        with open(pdf_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="FO_Report_{datetime.now().strftime("%Y%m%d")}.pdf"')
            msg.attach(part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, REPORT_RECIPIENT, msg.as_string())

        logger.info(f"Report email sent to {REPORT_RECIPIENT}")
        return True

    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False
