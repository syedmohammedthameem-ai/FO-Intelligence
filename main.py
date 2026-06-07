import os
import logging
import threading
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from data.stock_scanner import scan_fno_stocks, get_short_term_setups, get_long_term_candidates
from data.forex_data import get_macro_summary
from data.news_fetcher import fetch_india_market_news, fetch_global_news
from analysis.news_sentiment import get_market_sentiment_from_news
from analysis.nifty_analyzer import full_nifty_analysis
from report.pdf_generator import generate_report
from report.email_sender import send_report_email
from alerts.telegram_bot import send_market_open_summary, send_eod_summary
from analysis.ai_narrator import generate_eod_narrative
from alerts.monitor import run_realtime_monitor
from config import FNO_BUDGET, SHORT_TERM_BUDGET, LONG_TERM_BUDGET

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("fo_intelligence.log"),
    ],
)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)


def generate_and_send_report():
    logger.info("=== Starting EOD report generation ===")
    try:
        logger.info("Fetching macro data...")
        macro = get_macro_summary()

        logger.info("Fetching news...")
        india_news = fetch_india_market_news()
        global_news = fetch_global_news()
        news_sentiment = get_market_sentiment_from_news(india_news, global_news)

        logger.info("Running NIFTY F&O analysis...")
        nifty = full_nifty_analysis(budget=FNO_BUDGET)

        logger.info("Scanning F&O stocks...")
        scan_results = scan_fno_stocks()

        logger.info("Generating short-term setups...")
        short_term = get_short_term_setups(scan_results, budget=SHORT_TERM_BUDGET)

        logger.info("Generating long-term candidates...")
        long_term = get_long_term_candidates(budget=LONG_TERM_BUDGET)

        report_data = {
            "macro": macro,
            "news_sentiment": news_sentiment,
            "nifty": nifty,
            "scan_results": scan_results,
            "short_term": short_term,
            "long_term": long_term,
        }

        logger.info("Generating AI market narrative...")
        report_data["ai_narrative"] = generate_eod_narrative(report_data)

        output_path = os.path.join(
            REPORTS_DIR,
            f"FO_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        )

        logger.info("Generating PDF...")
        generate_report(report_data, output_path)

        logger.info("Sending email...")
        send_report_email(output_path, nifty, news_sentiment)

        strategy = nifty.get("suggested_strategy", {}).get("name", "N/A")
        send_eod_summary(nifty["spot"], nifty["technicals"]["change_pct"], nifty["pcr"], strategy)

        logger.info("=== Report generation complete ===")

    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)


def market_open_alert():
    try:
        macro = get_macro_summary()
        india_news = fetch_india_market_news()
        global_news = fetch_global_news()
        sentiment = get_market_sentiment_from_news(india_news, global_news)
        nifty = full_nifty_analysis(FNO_BUDGET)

        global_change = 0.0
        indices = macro.get("global_indices", [])
        sp500 = next((i for i in indices if i["index"] == "S&P 500"), None)
        if sp500:
            global_change = sp500["change_pct"]

        send_market_open_summary(nifty["spot"], global_change, sentiment["overall"])
    except Exception as e:
        logger.error(f"Market open alert failed: {e}")


def start_monitor_thread():
    t = threading.Thread(target=run_realtime_monitor, kwargs={"interval_seconds": 300}, daemon=True)
    t.start()
    logger.info("Real-time monitor thread started.")


def main():
    scheduler = BlockingScheduler(timezone=IST)

    # Daily EOD report at 4:00 PM IST (Mon–Fri)
    scheduler.add_job(
        generate_and_send_report,
        CronTrigger(hour=16, minute=0, day_of_week="mon-fri", timezone=IST),
        id="eod_report",
        name="EOD F&O Report",
        max_instances=1,
    )

    # Market open alert at 9:10 AM IST (Mon–Fri)
    scheduler.add_job(
        market_open_alert,
        CronTrigger(hour=9, minute=10, day_of_week="mon-fri", timezone=IST),
        id="market_open",
        name="Market Open Alert",
        max_instances=1,
    )

    # Start real-time monitor in background thread
    start_monitor_thread()

    logger.info("Scheduler started. EOD report at 4:00 PM IST | Market open alert at 9:10 AM IST")
    logger.info("Real-time monitor running every 5 minutes during market hours.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        # Manually trigger report for testing
        logger.info("Manual report trigger...")
        generate_and_send_report()
    else:
        main()
