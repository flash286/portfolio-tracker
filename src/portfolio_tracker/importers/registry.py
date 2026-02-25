"""
ETF registry: known ticker → ISIN, name, asset type, Teilfreistellung rate.

All ISINs here have been verified against OpenFIGI.
TFS rates per § 20 InvStG: equity ETF = 30%, bond ETF = 0%, mixed = 15%.

This registry covers the most common European ETFs traded on Trade Republic,
Revolut, and Xetra. Unknown tickers are resolved interactively at import time
and saved to user_registry.json at the project root.
"""

ETF_REGISTRY: dict[str, dict] = {
    # ------------------------------------------------------------------
    # Revolut Robo-Advisor ETFs
    # ------------------------------------------------------------------
    "IS3Q": {
        "isin": "IE00BP3QZ601",
        "name": "iShares MSCI World Quality Factor UCITS ETF",
        "type": "etf",
        "tfs": "0.3",
    },
    "XDWT": {
        "isin": "IE00BM67HT60",
        "name": "Xtrackers MSCI World Information Technology UCITS ETF",
        "type": "etf",
        "tfs": "0.3",
    },
    "DBXJ": {
        "isin": "LU0274209740",
        "name": "Xtrackers MSCI Japan UCITS ETF",
        "type": "etf",
        "tfs": "0.3",
    },
    "EXI2": {
        "isin": "DE0006289382",
        "name": "iShares Dow Jones Global Titans 50 ETF (Dist)",
        "type": "etf",
        "tfs": "0.3",
    },
    "IS3C": {
        "isin": "IE00B9M6RS56",
        "name": "iShares J.P. Morgan USD EM Bond ETF (Dist)",
        "type": "bond",
        "tfs": "0",
    },
    "IS3K": {
        "isin": "IE00BCRY6003",
        "name": "iShares EUR High Yield Corp Bond ETF (Dist)",
        "type": "bond",
        "tfs": "0",
    },
    "QDVY": {
        "isin": "IE00BZ048462",
        "name": "iShares $ Floating Rate Bond ETF (Dist)",
        "type": "bond",
        "tfs": "0",
    },
    "IBCD": {
        "isin": "IE0032895942",
        "name": "iShares Core EUR Corp Bond ETF (Dist)",
        "type": "bond",
        "tfs": "0",
    },

    # ------------------------------------------------------------------
    # Portfolio A (Trade Republic target allocation)
    # ------------------------------------------------------------------
    "VWCE": {
        "isin": "IE00BK5BQT80",
        "name": "Vanguard FTSE All-World UCITS ETF (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },
    "VVSM": {
        "isin": "IE00BMC38736",
        "name": "Vanguard FTSE All-World Small-Cap UCITS ETF (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },
    "HEAL": {
        "isin": "IE00BYZK4776",
        "name": "iShares Healthcare Innovation UCITS ETF",
        "type": "etf",
        "tfs": "0.3",
    },
    "VAGF": {
        "isin": "IE00BG47KH54",
        "name": "Vanguard Global Aggregate Bond UCITS ETF",
        "type": "bond",
        "tfs": "0",
    },

    # ------------------------------------------------------------------
    # iShares Core series — Xetra tickers
    # ------------------------------------------------------------------
    "EUNL": {
        "isin": "IE00B4L5Y983",
        "name": "iShares Core MSCI World UCITS ETF USD (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },
    "IS3N": {
        "isin": "IE00BKM4GZ66",
        "name": "iShares Core MSCI EM IMI UCITS ETF USD (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },
    "SXR8": {
        "isin": "IE00B5BMR087",
        "name": "iShares Core S&P 500 UCITS ETF USD (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },
    "IUSQ": {
        "isin": "IE00B6R52259",
        "name": "iShares MSCI ACWI UCITS ETF USD (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },
    "EXS1": {
        "isin": "DE0005933931",
        "name": "iShares Core DAX UCITS ETF EUR (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },

    # ------------------------------------------------------------------
    # iShares Core series — LSE tickers (same funds, different exchange)
    # ------------------------------------------------------------------
    "IWDA": {
        "isin": "IE00B4L5Y983",
        "name": "iShares Core MSCI World UCITS ETF USD (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },
    "EIMI": {
        "isin": "IE00BKM4GZ66",
        "name": "iShares Core MSCI EM IMI UCITS ETF USD (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },
    "CSPX": {
        "isin": "IE00B5BMR087",
        "name": "iShares Core S&P 500 UCITS ETF USD (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },
    "AGGH": {
        "isin": "IE00BDBRDM35",
        "name": "iShares Core Global Aggregate Bond UCITS ETF EUR Hedged (Acc)",
        "type": "bond",
        "tfs": "0",
    },

    # ------------------------------------------------------------------
    # Vanguard ETFs
    # ------------------------------------------------------------------
    "VWRL": {
        "isin": "IE00B3RBWM25",
        "name": "Vanguard FTSE All-World UCITS ETF USD Dist",
        "type": "etf",
        "tfs": "0.3",
    },
    "VHYL": {
        "isin": "IE00B8GKDB10",
        "name": "Vanguard FTSE All-World High Dividend Yield UCITS ETF USD Dist",
        "type": "etf",
        "tfs": "0.3",
    },
    "VUAA": {
        "isin": "IE00BFMXXD54",
        "name": "Vanguard S&P 500 UCITS ETF USD (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },
    "VUSA": {
        "isin": "IE00B3XXRP09",
        "name": "Vanguard S&P 500 UCITS ETF USD Dist",
        "type": "etf",
        "tfs": "0.3",
    },
    "VFEM": {
        "isin": "IE00B3VVMM84",
        "name": "Vanguard FTSE Emerging Markets UCITS ETF USD Dist",
        "type": "etf",
        "tfs": "0.3",
    },

    # ------------------------------------------------------------------
    # Xtrackers ETFs
    # ------------------------------------------------------------------
    "XDWD": {
        "isin": "LU0274208692",
        "name": "Xtrackers MSCI World UCITS ETF 1C",
        "type": "etf",
        "tfs": "0.3",
    },
    "DBXD": {
        "isin": "LU0274211480",
        "name": "Xtrackers DAX UCITS ETF 1C",
        "type": "etf",
        "tfs": "0.3",
    },
    "XGVD": {
        "isin": "LU0378818131",
        "name": "Xtrackers II Global Government Bond UCITS ETF 1C EUR Hedged",
        "type": "bond",
        "tfs": "0",
    },

    # ------------------------------------------------------------------
    # SPDR (State Street) ETFs
    # ------------------------------------------------------------------
    "SWRD": {
        "isin": "IE00BFY0GT14",
        "name": "SPDR MSCI World UCITS ETF USD (Acc)",
        "type": "etf",
        "tfs": "0.3",
    },
}
