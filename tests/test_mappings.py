"""market symbol / entity マッピングと設定ファイルの整合性テスト。"""
from pipeline import config as cfg


def test_market_symbols_unique_and_shaped():
    symbols = cfg.markets()["symbols"]
    canonicals = [s["canonical"] for s in symbols]
    assert len(canonicals) == len(set(canonicals)), "canonical 重複"
    for s in symbols:
        assert s["asset"] in {"fx", "index", "equity", "rate", "commodity", "crypto"}
        assert isinstance(s.get("providers", {}), dict)


def test_enabled_symbols_have_provider():
    known_providers = set(cfg.markets()["providers"].keys())
    for s in cfg.markets()["symbols"]:
        if s.get("enabled") is False:
            continue
        provs = s.get("providers", {})
        assert provs, f"{s['canonical']} は enabled だが provider 未定義"
        for p in provs:
            assert p in known_providers, f"{s['canonical']} の provider {p} が未定義"


def test_entity_tickers_resolve_to_market_symbols():
    canonicals = {s["canonical"] for s in cfg.markets()["symbols"]}
    for ent in cfg.entities():
        for t in ent.get("tickers", []):
            assert t in canonicals, f"entity {ent['id']} の ticker {t} が markets.yaml に無い"


def test_entities_have_required_fields():
    ids = set()
    for ent in cfg.entities():
        assert ent["id"] not in ids, f"entity id 重複: {ent['id']}"
        ids.add(ent["id"])
        assert ent.get("aliases"), f"entity {ent['id']} に alias が無い"


def test_rss_sources_shape():
    for s in cfg.sources()["rss"]:
        assert s["method"] in {"rss", "api", "none"}
        if s["method"] == "none":
            assert s.get("enabled") is False, \
                f"{s['id']}: method none は enabled: false であるべき (スクレイピング禁止)"
        assert 0 <= float(s.get("quality", 0.5)) <= 1


def test_scoring_weights_sum_to_one():
    weights = cfg.scoring()["weights"]
    assert abs(sum(weights.values()) - 1.0) < 1e-6
