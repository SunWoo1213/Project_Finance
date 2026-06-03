from app.core.log_sanitizer import redact_secrets


def test_redacts_data_go_kr_service_key_query_param():
    url = (
        "Client error '404 Not Found' for url "
        "'https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
        "?serviceKey=a0baf4653abbfcfc1a4f05eb22d110d52f40f61c6583664e72f8e2f9cf034fd3"
        "&resultType=json&pageNo=1'"
    )

    sanitized = redact_secrets(url)

    assert "a0baf4653abbfcfc1a4f05eb22d110d52f40f61c6583664e72f8e2f9cf034fd3" not in sanitized
    assert "serviceKey=***" in sanitized
    # 비민감 파라미터는 보존된다.
    assert "resultType=json" in sanitized


def test_redacts_finnhub_token_and_fred_api_key_query_params():
    finnhub = redact_secrets("https://finnhub.io/api/v1/quote?symbol=NVDA&token=SECRETTOKEN123")
    fred = redact_secrets(
        "https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key=FREDKEY9876&file_type=json"
    )

    assert "SECRETTOKEN123" not in finnhub
    assert "token=***" in finnhub
    assert "FREDKEY9876" not in fred
    assert "api_key=***" in fred
    assert "file_type=json" in fred


def test_redacts_extra_literal_secret_in_url_path():
    # ECOS는 키를 URL 경로에 넣는다: /api/StatisticSearch/{KEY}/json/...
    ecos_key = "ECOSPATHKEY4567"
    text = f"HTTPStatusError for url 'https://ecos.bok.or.kr/api/StatisticSearch/{ecos_key}/json/kr/1/100/817Y002/D'"

    sanitized = redact_secrets(text, [ecos_key])

    assert ecos_key not in sanitized
    assert "***" in sanitized


def test_ignores_empty_and_short_extra_secrets():
    text = "no secrets here"
    # 빈 값/너무 짧은 값은 무시되어 본문이 깨지지 않는다.
    assert redact_secrets(text, ["", "ab"]) == text
