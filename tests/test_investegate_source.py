from ingestion.investegate_daily import InvestegateDailyAIMSource


def test_parse_investegate_aim_rows():
    html = """
    <table>
      <tr>
        <td>21 Aug 2026 07:00 AM</td>
        <td>RNS</td>
        <td>Springfield Properties (SPR)</td>
        <td><a href="/announcement/rns/springfield-properties--spr/trading-update/12345">Trading Update</a></td>
      </tr>
      <tr>
        <td>21 Aug 2026 07:01 AM</td>
        <td>NEWS</td>
        <td>Ignore Me (IGN)</td>
        <td><a href="/news/ignore">Ordinary news</a></td>
      </tr>
    </table>
    """

    rows = InvestegateDailyAIMSource._parse_page(html)

    assert len(rows) == 1
    published, ticker, company, headline, source_url = rows[0]
    assert published.strftime("%Y-%m-%d %H:%M") == "2026-08-21 07:00"
    assert ticker == "SPR"
    assert company == "Springfield Properties"
    assert headline == "Trading Update"
    assert source_url == (
        "https://www.investegate.co.uk/announcement/rns/"
        "springfield-properties--spr/trading-update/12345"
    )
