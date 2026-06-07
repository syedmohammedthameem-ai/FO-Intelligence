import os
import io
import logging
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

logger = logging.getLogger(__name__)

# Color palette
DARK_BG = colors.HexColor("#0D1117")
ACCENT_GREEN = colors.HexColor("#00C853")
ACCENT_RED = colors.HexColor("#FF1744")
ACCENT_AMBER = colors.HexColor("#FFD600")
ACCENT_BLUE = colors.HexColor("#2979FF")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
MID_GRAY = colors.HexColor("#90A4AE")
DARK_TEXT = colors.HexColor("#212121")
WHITE = colors.white


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", fontSize=22, textColor=DARK_TEXT, alignment=TA_CENTER, spaceAfter=4, fontName="Helvetica-Bold"),
        "subtitle": ParagraphStyle("subtitle", fontSize=11, textColor=MID_GRAY, alignment=TA_CENTER, spaceAfter=2),
        "section": ParagraphStyle("section", fontSize=14, textColor=ACCENT_BLUE, fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4),
        "body": ParagraphStyle("body", fontSize=9, textColor=DARK_TEXT, leading=14, spaceAfter=3),
        "small": ParagraphStyle("small", fontSize=8, textColor=MID_GRAY, leading=12),
        "bullish": ParagraphStyle("bullish", fontSize=10, textColor=ACCENT_GREEN, fontName="Helvetica-Bold"),
        "bearish": ParagraphStyle("bearish", fontSize=10, textColor=ACCENT_RED, fontName="Helvetica-Bold"),
        "neutral": ParagraphStyle("neutral", fontSize=10, textColor=ACCENT_AMBER, fontName="Helvetica-Bold"),
        "strategy_box": ParagraphStyle("strategy_box", fontSize=9, textColor=DARK_TEXT, leading=13, leftIndent=6),
    }


def _sentiment_style(sentiment: str, s: dict):
    if "BULL" in sentiment.upper():
        return s["bullish"]
    elif "BEAR" in sentiment.upper():
        return s["bearish"]
    return s["neutral"]


def _color_val(val: float):
    return ACCENT_GREEN if val >= 0 else ACCENT_RED


def _table(data: list, col_widths=None, header_bg=ACCENT_BLUE) -> Table:
    t = Table(data, colWidths=col_widths)
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.3, MID_GRAY),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    t.setStyle(style)
    return t


def generate_report(data: dict, output_path: str) -> str:
    """
    Master PDF report generator.
    data keys: nifty, short_term, long_term, macro, news_sentiment, scan_results
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    s = _styles()
    story = []
    today = datetime.now().strftime("%d %B %Y")
    generated_at = datetime.now().strftime("%H:%M IST")

    # ─── HEADER ───────────────────────────────────────────────────────────────
    story.append(Paragraph("F&O INTELLIGENCE REPORT", s["title"]))
    story.append(Paragraph(f"{today}  |  Generated at {generated_at}", s["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT_BLUE, spaceAfter=8))

    # ─── 0. AI MARKET BRIEF ───────────────────────────────────────────────────
    ai_narrative = data.get("ai_narrative", "")
    if ai_narrative:
        story.append(Paragraph("AI Market Brief", s["section"]))
        ai_box_style = ParagraphStyle(
            "ai_box",
            fontSize=9,
            textColor=DARK_TEXT,
            leading=15,
            leftIndent=8,
            rightIndent=8,
            spaceBefore=4,
            spaceAfter=4,
            backColor=colors.HexColor("#E8F4FD"),
            borderPadding=(6, 8, 6, 8),
        )
        import re
        for para in ai_narrative.split("\n\n"):
            if para.strip():
                cleaned = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', para.strip())
                story.append(Paragraph(cleaned, ai_box_style))
        story.append(Spacer(1, 8))

    # ─── 1. MACRO SNAPSHOT ────────────────────────────────────────────────────
    macro = data.get("macro", {})
    story.append(Paragraph("1. Macro Snapshot", s["section"]))

    macro_rows = [["Indicator", "Value", "Change", "Signal"]]
    usdinr = macro.get("usdinr", {})
    gold = macro.get("gold", {})
    crude = macro.get("crude", {})

    if usdinr:
        chg = usdinr.get("change_pct", 0)
        macro_rows.append(["USD/INR", f"₹{usdinr.get('rate', 0):.4f}",
                           f"{chg:+.3f}%", usdinr.get("signal", "")[:50]])
    if gold:
        chg = gold.get("change_pct", 0)
        macro_rows.append(["Gold (USD/oz)", f"${gold.get('price_usd', 0):.2f}",
                           f"{chg:+.2f}%", gold.get("signal", "")[:50]])
    if crude:
        chg = crude.get("change_pct", 0)
        macro_rows.append(["Crude (USD/bbl)", f"${crude.get('price_usd', 0):.2f}",
                           f"{chg:+.2f}%", crude.get("signal", "")[:50]])

    story.append(_table(macro_rows, col_widths=[3.5 * cm, 2.5 * cm, 2 * cm, 9 * cm]))
    story.append(Spacer(1, 6))

    # Global indices
    indices = macro.get("global_indices", [])
    if indices:
        idx_rows = [["Index", "Value", "Change %"]]
        for idx in indices:
            chg = idx["change_pct"]
            idx_rows.append([idx["index"], f"{idx['value']:,.2f}", f"{chg:+.2f}%"])
        story.append(_table(idx_rows, col_widths=[6 * cm, 5 * cm, 5 * cm]))

    story.append(Spacer(1, 8))

    # ─── 2. NEWS SENTIMENT ────────────────────────────────────────────────────
    news = data.get("news_sentiment", {})
    story.append(Paragraph("2. News Sentiment Analysis", s["section"]))
    overall = news.get("overall", "NEUTRAL")
    score = news.get("combined_score", 0)
    story.append(Paragraph(
        f"Overall Market Sentiment: <b>{overall}</b>  (Score: {score:+.3f})",
        _sentiment_style(overall, s)
    ))

    india_news = news.get("india", {}).get("articles", [])[:5]
    if india_news:
        story.append(Paragraph("Top India Market Headlines:", s["body"]))
        news_rows = [["Sentiment", "Headline", "Source"]]
        for a in india_news:
            sent = a.get("sentiment", "NEUTRAL")
            emoji = a.get("emoji", "→")
            title = (a.get("title", "")[:80] + "…") if len(a.get("title", "")) > 80 else a.get("title", "")
            news_rows.append([f"{emoji} {sent}", title, a.get("source", "")[:20]])
        story.append(_table(news_rows, col_widths=[2.5 * cm, 12 * cm, 3 * cm]))

    story.append(Spacer(1, 8))

    # ─── 3. NIFTY F&O ANALYSIS ────────────────────────────────────────────────
    nifty = data.get("nifty", {})
    story.append(Paragraph("3. NIFTY F&O Analysis", s["section"]))

    if nifty:
        spot = nifty.get("spot", 0)
        trend = nifty.get("trend", "NEUTRAL")
        tech = nifty.get("technicals", {})
        story.append(Paragraph(
            f"NIFTY Spot: <b>{spot:,.2f}</b>  |  Trend: <b>{trend}</b>  |  Change: {tech.get('change_pct', 0):+.2f}%  |  RSI: {tech.get('rsi', 0):.1f}",
            _sentiment_style(trend, s)
        ))
        story.append(Spacer(1, 4))

        # Technical levels table
        tech_rows = [["Indicator", "Value"]]
        tech_rows += [
            ["EMA 20", f"{tech.get('ema20', 0):,.2f}"],
            ["EMA 50", f"{tech.get('ema50', 0):,.2f}"],
            ["EMA 200", f"{tech.get('ema200', 0):,.2f}"],
            ["BB Upper", f"{tech.get('bb_upper', 0):,.2f}"],
            ["BB Lower", f"{tech.get('bb_lower', 0):,.2f}"],
            ["RSI (14)", f"{tech.get('rsi', 0):.1f}"],
        ]
        story.append(_table(tech_rows, col_widths=[5 * cm, 5 * cm]))
        story.append(Spacer(1, 6))

        # Options data
        opt_rows = [["Parameter", "Weekly", "Monthly"]]
        opt_rows += [
            ["Expiry", nifty.get("weekly_expiry", ""), nifty.get("monthly_expiry", "")],
            ["DTE", str(nifty.get("dte_weekly", "")), str(nifty.get("dte_monthly", ""))],
            ["ATM Strike", str(nifty.get("atm_strike", "")), str(nifty.get("atm_strike", ""))],
            ["ATM CE IV", f"{nifty.get('atm_ce_iv_pct', 0):.2f}%", f"{nifty.get('atm_ce_iv_pct', 0):.2f}%"],
            ["ATM PE IV", f"{nifty.get('atm_pe_iv_pct', 0):.2f}%", f"{nifty.get('atm_pe_iv_pct', 0):.2f}%"],
            ["CE Delta", f"{nifty.get('weekly_greeks', {}).get('ce', {}).get('delta', 0):.4f}",
             f"{nifty.get('monthly_greeks', {}).get('ce', {}).get('delta', 0):.4f}"],
            ["PE Delta", f"{nifty.get('weekly_greeks', {}).get('pe', {}).get('delta', 0):.4f}",
             f"{nifty.get('monthly_greeks', {}).get('pe', {}).get('delta', 0):.4f}"],
            ["CE Theta/day", f"₹{nifty.get('weekly_greeks', {}).get('ce', {}).get('theta', 0):.2f}",
             f"₹{nifty.get('monthly_greeks', {}).get('ce', {}).get('theta', 0):.2f}"],
            ["PE Theta/day", f"₹{nifty.get('weekly_greeks', {}).get('pe', {}).get('theta', 0):.2f}",
             f"₹{nifty.get('monthly_greeks', {}).get('pe', {}).get('theta', 0):.2f}"],
            ["Vega (CE)", f"₹{nifty.get('weekly_greeks', {}).get('ce', {}).get('vega', 0):.2f}",
             f"₹{nifty.get('monthly_greeks', {}).get('ce', {}).get('vega', 0):.2f}"],
        ]
        story.append(_table(opt_rows, col_widths=[5 * cm, 5 * cm, 5 * cm]))
        story.append(Spacer(1, 6))

        # PCR + Max Pain + OI levels
        story.append(Paragraph(
            f"PCR: <b>{nifty.get('pcr', 0):.3f}</b>  |  IV Rank: <b>{nifty.get('iv_rank', 0):.1f}%</b>  |  IV Percentile: <b>{nifty.get('iv_percentile', 0):.1f}%</b>  |  Max Pain: <b>{nifty.get('max_pain', 0):,.0f}</b>",
            s["body"]
        ))
        story.append(Paragraph(f"PCR Signal: {nifty.get('pcr_signal', '')}", s["small"]))

        oi_sup = ", ".join([str(x) for x in nifty.get("oi_support", [])])
        oi_res = ", ".join([str(x) for x in nifty.get("oi_resistance", [])])
        story.append(Paragraph(f"OI Support Levels: {oi_sup}  |  OI Resistance Levels: {oi_res}", s["body"]))
        story.append(Spacer(1, 6))

        # Strategy box
        strat = nifty.get("suggested_strategy", {})
        if strat:
            story.append(Paragraph(f"Suggested Strategy: <b>{strat.get('name', '')}</b>", s["section"]))
            story.append(Paragraph(strat.get("rationale", ""), s["strategy_box"]))
            story.append(Paragraph(f"Legs: {strat.get('legs', '')}", s["strategy_box"]))
            story.append(Paragraph(f"Ideal DTE: {strat.get('ideal_dte', '')}", s["strategy_box"]))

    story.append(Spacer(1, 8))

    # ─── 4. SHORT-TERM STOCK SETUPS ───────────────────────────────────────────
    short_term = data.get("short_term", [])
    story.append(Paragraph("4. Short-Term Stock Setups (Aggressive | 1-5 Days)", s["section"]))

    if short_term:
        st_rows = [["Stock", "Dir", "Entry", "SL", "T1", "T2", "R:R", "Vol Spike", "Score"]]
        for t in short_term:
            st_rows.append([
                t["symbol"], t["direction"],
                f"₹{t['entry']}", f"₹{t['sl']}",
                f"₹{t['target1']}", f"₹{t['target2']}",
                f"{t['risk_reward']}x", f"{t['volume_spike']}x",
                str(t["score"]),
            ])
        story.append(_table(st_rows, col_widths=[2.5*cm, 1.2*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.5*cm, 2*cm, 1.5*cm]))
        story.append(Spacer(1, 4))
        for t in short_term:
            story.append(Paragraph(f"<b>{t['symbol']}</b>: {t['reasoning']}", s["small"]))
    else:
        story.append(Paragraph("No high-conviction short-term setups found today.", s["small"]))

    story.append(Spacer(1, 8))

    # ─── 5. LONG-TERM STOCK PLAYS ─────────────────────────────────────────────
    long_term = data.get("long_term", [])
    story.append(Paragraph("5. Long-Term Stock Plays (Moderate | 4-12 Weeks)", s["section"]))

    if long_term:
        lt_rows = [["Stock", "Entry", "SL", "Target", "Hold", "EMA20", "EMA50", "Score"]]
        for t in long_term:
            lt_rows.append([
                t["symbol"], f"₹{t['entry']}", f"₹{t['sl']}",
                f"₹{t['target']}", t["hold"],
                f"₹{t['ema20']}", f"₹{t['ema50']}", str(t["score"]),
            ])
        story.append(_table(lt_rows, col_widths=[2.5*cm, 2*cm, 2*cm, 2*cm, 2.5*cm, 2*cm, 2*cm, 1.5*cm]))
        story.append(Spacer(1, 4))
        for t in long_term:
            story.append(Paragraph(f"<b>{t['symbol']}</b>: {t['reasoning']}", s["small"]))
    else:
        story.append(Paragraph("No long-term setups passing filters today.", s["small"]))

    story.append(Spacer(1, 8))

    # ─── 6. TOP VOLUME/VOLATILITY MOVERS ──────────────────────────────────────
    scan = data.get("scan_results", [])
    story.append(Paragraph("6. Top Volume + Volatility Movers (NSE F&O Universe)", s["section"]))

    if not scan.empty if hasattr(scan, "empty") else not scan:
        story.append(Paragraph("No significant movers today.", s["small"]))
    else:
        scan_list = scan.head(10).to_dict("records") if hasattr(scan, "head") else scan[:10]
        scan_rows = [["Stock", "LTP", "Chg%", "Vol Spike", "ATR%", "Score"]]
        for r in scan_list:
            scan_rows.append([
                r["symbol"], f"₹{r['ltp']}", f"{r['change_pct']:+.2f}%",
                f"{r['volume_spike']}x", f"{r['atr_pct']}%", str(r["momentum_score"]),
            ])
        story.append(_table(scan_rows, col_widths=[3*cm, 2.5*cm, 2*cm, 2.5*cm, 2*cm, 2*cm]))

    story.append(Spacer(1, 8))

    # ─── DISCLAIMER ────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceBefore=10))
    story.append(Paragraph(
        "DISCLAIMER: This report is for educational and informational purposes only. "
        "It does not constitute financial advice. All trades carry risk. "
        "Please consult a SEBI-registered advisor before investing.",
        s["small"]
    ))

    doc.build(story)
    logger.info(f"Report saved to {output_path}")
    return output_path
