"""
股票池配置 + Peer Group定义
200只精选美股 + 手动定义的可比公司
"""

# ============================================
# Telegram配置 (使用环境变量，保护敏感信息)
# ============================================
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
# Cloudflare Workers webhook (推荐)
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")

# ============================================
# 评分权重配置
# ============================================
SCORE_WEIGHTS = {
    "valuation": 0.30,      # 估值因子
    "technical": 0.25,      # 技术因子
    "momentum": 0.20,       # 价格动量
    "relative_strength": 0.15,  # 相对强度
    "volatility": 0.10      # 波动率状态
}

# ============================================
# 预警阈值
# ============================================
ALERT_THRESHOLDS = {
    "bottom_score": 75,     # 综合分 > 75 触发底部预警
    "top_score": 25,        # 综合分 < 25 触发顶部预警
    "valuation_bottom": 70, # 估值分 > 70 才能触发底部
    "valuation_top": 30,    # 估值分 < 30 才能触发顶部
}

# ============================================
# 手动定义的Peer Groups (更精准的可比公司)
# 格式: "TICKER": ["PEER1", "PEER2", ...]
# 如果股票不在这里，会fallback到GICS行业分类
# ============================================
PEER_GROUPS = {
    # ========== MAG7 + 大型科技 ==========
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "ORCL", "CRM"],
    "GOOGL": ["META", "MSFT", "AMZN", "SNAP", "PINS"],
    "AMZN": ["WMT", "COST", "TGT", "BABA", "JD"],
    "META": ["GOOGL", "SNAP", "PINS", "TTWO", "EA"],
    "TSLA": ["RIVN", "LCID", "NIO", "GM", "F"],
    "NVDA": ["AMD", "INTC", "AVGO", "MRVL", "QCOM"],
    
    # ========== 半导体 ==========
    "AMD": ["NVDA", "INTC", "QCOM", "MRVL"],
    "INTC": ["AMD", "NVDA", "TXN", "QCOM"],
    "AVGO": ["QCOM", "TXN", "MRVL", "ADI"],
    "QCOM": ["AVGO", "MRVL", "SWKS", "QRVO"],
    "MU": ["WDC", "STX", "NXPI"],
    "MRVL": ["AVGO", "QCOM", "SWKS"],
    "AMAT": ["LRCX", "KLAC", "ASML"],
    "LRCX": ["AMAT", "KLAC", "ASML"],
    "KLAC": ["AMAT", "LRCX", "ASML"],
    "ASML": ["AMAT", "LRCX", "KLAC"],
    "ARM": ["NVDA", "AMD", "QCOM"],
    "TSM": ["INTC", "ASML", "AMAT"],
    "SMCI": ["DELL", "HPE", "IBM"],
    
    # ========== 软件/SaaS ==========
    "CRM": ["NOW", "WDAY", "SAP", "ORCL"],
    "NOW": ["CRM", "WDAY", "SNOW", "DDOG"],
    "WDAY": ["CRM", "NOW", "SAP"],
    "SNOW": ["DDOG", "MDB", "PLTR", "DBX"],
    "PLTR": ["SNOW", "DDOG", "AI", "PATH"],
    "DDOG": ["SNOW", "NOW", "SPLK", "DT"],
    "CRWD": ["PANW", "ZS", "FTNT", "S"],
    "PANW": ["CRWD", "ZS", "FTNT", "CHKP"],
    "ZS": ["CRWD", "PANW", "FTNT", "NET"],
    "NET": ["FSLY", "ZS", "AKAM"],
    "MDB": ["SNOW", "DDOG", "ESTC"],
    "SHOP": ["SQ", "PYPL", "MELI"],
    "SQ": ["PYPL", "SHOP", "AFRM"],
    "ADBE": ["CRM", "NOW", "ORCL"],
    
    # ========== 金融 ==========
    "JPM": ["BAC", "GS", "MS", "C", "WFC"],
    "BAC": ["JPM", "C", "WFC", "USB"],
    "GS": ["MS", "JPM", "SCHW"],
    "MS": ["GS", "JPM", "SCHW"],
    "V": ["MA", "AXP", "PYPL"],
    "MA": ["V", "AXP", "PYPL"],
    "AXP": ["V", "MA", "DFS"],
    "BLK": ["SCHW", "TROW", "BEN"],
    "SCHW": ["MS", "GS", "IBKR"],
    
    # ========== 消费 ==========
    "COST": ["WMT", "TGT", "AMZN"],
    "WMT": ["COST", "TGT", "AMZN", "DG"],
    "HD": ["LOW", "WMT", "COST"],
    "LOW": ["HD", "WMT"],
    "NKE": ["LULU", "UAA", "DECK"],
    "LULU": ["NKE", "UAA", "DECK"],
    "SBUX": ["MCD", "CMG", "DPZ"],
    "MCD": ["SBUX", "CMG", "YUM", "QSR"],
    "DIS": ["NFLX", "WBD", "CMCSA", "PARA"],
    "NFLX": ["DIS", "WBD", "PARA", "SPOT"],
    "BKNG": ["EXPE", "ABNB", "MAR"],
    "ABNB": ["BKNG", "EXPE", "MAR"],
    
    # ========== 医疗/生物科技 ==========
    "UNH": ["CVS", "CI", "ELV", "HUM"],
    "LLY": ["NVO", "PFE", "MRK", "ABBV"],
    "JNJ": ["PFE", "MRK", "ABBV", "BMY"],
    "PFE": ["MRK", "JNJ", "ABBV", "BMY"],
    "ABBV": ["PFE", "MRK", "JNJ", "BMY"],
    "MRK": ["PFE", "JNJ", "ABBV", "LLY"],
    "TMO": ["DHR", "A", "BDX"],
    "DHR": ["TMO", "A", "ISRG"],
    "ISRG": ["SYK", "MDT", "ABT"],
    "VRTX": ["REGN", "BIIB", "GILD"],
    "REGN": ["VRTX", "BIIB", "GILD"],
    
    # ========== 工业 ==========
    "CAT": ["DE", "CNH", "AGCO"],
    "DE": ["CAT", "CNH", "AGCO"],
    "UNP": ["CSX", "NSC"],
    "HON": ["MMM", "EMR", "ROK"],
    "GE": ["HON", "RTX", "BA"],
    "BA": ["LMT", "RTX", "GD", "NOC"],
    "LMT": ["RTX", "BA", "GD", "NOC"],
    "RTX": ["LMT", "BA", "GD", "NOC"],
    
    # ========== 能源 ==========
    "XOM": ["CVX", "COP", "EOG", "SLB"],
    "CVX": ["XOM", "COP", "EOG", "OXY"],
    "COP": ["XOM", "CVX", "EOG", "DVN"],
    
    # ========== 新兴成长股 ==========
    "COIN": ["HOOD", "MARA", "RIOT", "MSTR"],
    "HOOD": ["COIN", "SCHW", "IBKR"],
    "RKLB": ["LUNR", "RDW", "SPCE"],
    "IONQ": ["RGTI", "QUBT"],
    "APP": ["TTD", "MGNI", "PUBM"],
    "CELH": ["MNST", "KO", "PEP"],
    "DUOL": ["CHGG", "COUR"],
    "AFRM": ["SQ", "PYPL", "UPST"],
    "UPST": ["AFRM", "SQ", "SOFI"],
    "SOFI": ["HOOD", "UPST", "LC"],
    
    # ========== 中概股 ==========
    "BABA": ["JD", "PDD", "BIDU"],
    "JD": ["BABA", "PDD", "VIPS"],
    "PDD": ["BABA", "JD", "VIPS"],
    "BIDU": ["BABA", "GOOGL", "META"],
    "NIO": ["TSLA", "XPEV", "LI", "RIVN"],
    "XPEV": ["NIO", "LI", "TSLA"],
    "LI": ["NIO", "XPEV", "TSLA"],
}

# ============================================
# 行业分类 (用于没有手动定义peer的股票)
# ============================================
SECTOR_MAPPING = {
    "Technology": [
        "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CSCO", "ACN", "ADBE", "CRM", 
        "AMD", "INTC", "QCOM", "TXN", "NOW", "IBM", "INTU", "AMAT", "LRCX",
        "MU", "KLAC", "ADI", "SNPS", "CDNS", "MRVL", "FTNT", "PANW", "CRWD",
        "WDAY", "SNOW", "DDOG", "ZS", "NET", "MDB", "PLTR", "SHOP", "SQ",
        "ARM", "TSM", "ASML", "SMCI"
    ],
    "Communication Services": [
        "GOOGL", "GOOG", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS",
        "CHTR", "EA", "TTWO", "WBD", "PARA", "SNAP", "PINS", "SPOT", "RBLX"
    ],
    "Consumer Discretionary": [
        "AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "TJX", "BKNG",
        "MAR", "CMG", "LULU", "DECK", "ORLY", "AZO", "ROST", "DG", "DLTR",
        "ABNB", "EXPE", "RCL", "CCL", "GM", "F", "RIVN", "LCID"
    ],
    "Consumer Staples": [
        "WMT", "COST", "PG", "KO", "PEP", "PM", "MO", "MDLZ", "CL", "KMB",
        "GIS", "K", "HSY", "SYY", "KR", "WBA", "MNST", "CELH"
    ],
    "Financials": [
        "JPM", "BAC", "WFC", "GS", "MS", "SCHW", "C", "AXP", "BLK", "SPGI",
        "CME", "ICE", "MCO", "CB", "PGR", "MET", "AIG", "TRV", "ALL", "AFL",
        "V", "MA", "PYPL", "COIN", "HOOD", "AFRM", "UPST", "SOFI"
    ],
    "Healthcare": [
        "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "DHR", "ABT", "BMY",
        "AMGN", "GILD", "ISRG", "CVS", "CI", "ELV", "HUM", "VRTX", "REGN",
        "BIIB", "ILMN", "DXCM", "IDXX", "ZTS", "SYK", "BSX", "MDT", "EW", "BDX"
    ],
    "Industrials": [
        "CAT", "HON", "UNP", "UPS", "RTX", "BA", "LMT", "GE", "DE", "MMM",
        "EMR", "ETN", "ITW", "PH", "ROK", "CMI", "NSC", "CSX", "FDX",
        "GD", "NOC", "TDG", "WM", "RSG"
    ],
    "Energy": [
        "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "VLO", "OXY", "DVN",
        "PXD", "HES", "HAL", "BKR", "KMI", "WMB", "OKE"
    ],
    "Materials": [
        "LIN", "APD", "SHW", "ECL", "DD", "NEM", "FCX", "NUE", "VMC", "MLM"
    ],
    "Real Estate": [
        "AMT", "PLD", "CCI", "EQIX", "PSA", "DLR", "O", "SPG", "WELL", "AVB"
    ],
    "Utilities": [
        "NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "PEG", "ED"
    ],
    "Crypto & Emerging": [
        "COIN", "HOOD", "MARA", "RIOT", "MSTR", "RKLB", "IONQ", "RGTI",
        "APP", "DUOL", "PATH", "AI"
    ]
}

# ============================================
# 200只精选股票池
# ============================================
STOCK_UNIVERSE = [
    # MAG7 + 大型科技 (15)
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", 
    "AVGO", "ORCL", "CRM", "ADBE", "NOW", "IBM", "CSCO", "ACN",
    
    # 半导体 (15)
    "AMD", "INTC", "QCOM", "MU", "MRVL", "AMAT", "LRCX", "KLAC", 
    "ASML", "ARM", "TSM", "TXN", "ADI", "NXPI", "SMCI",
    
    # 软件/SaaS/网络安全 (20)
    "WDAY", "SNOW", "PLTR", "DDOG", "CRWD", "PANW", "ZS", "FTNT",
    "NET", "MDB", "SHOP", "SQ", "INTU", "SNPS", "CDNS",
    "TEAM", "ZM", "OKTA", "TWLO", "DBX",
    
    # 金融 (20)
    "JPM", "BAC", "GS", "MS", "WFC", "C", "USB", "PNC",
    "V", "MA", "AXP", "PYPL", "BLK", "SCHW", "SPGI",
    "CME", "ICE", "MCO", "TFC", "COF",
    
    # 消费 (20)
    "COST", "WMT", "HD", "LOW", "TGT", "DG", "DLTR",
    "NKE", "LULU", "DECK", "SBUX", "MCD", "CMG", "YUM", "DPZ",
    "DIS", "NFLX", "BKNG", "ABNB", "EXPE",
    
    # 医疗/生物科技 (25)
    "UNH", "LLY", "JNJ", "PFE", "ABBV", "MRK", "BMY", "AMGN", "GILD",
    "TMO", "DHR", "ABT", "ISRG", "SYK", "MDT", "BSX", "EW", "BDX",
    "CVS", "CI", "ELV", "HUM",
    "VRTX", "REGN", "BIIB",
    
    # 工业 (15)
    "CAT", "DE", "UNP", "UPS", "HON", "GE", "MMM", "EMR",
    "BA", "LMT", "RTX", "GD", "NOC",
    "CSX", "NSC",
    
    # 能源 (10)
    "XOM", "CVX", "COP", "EOG", "SLB", "OXY", "DVN", "MPC", "PSX", "VLO",
    
    # 新兴成长股 (30)
    "COIN", "HOOD", "RKLB", "IONQ", "SMCI", "APP", "CELH", "DUOL",
    "AFRM", "UPST", "SOFI", "MARA", "RIOT", "MSTR",
    "SNAP", "PINS", "SPOT", "RBLX", "U", "TTWO", "EA",
    "PATH", "AI", "DOCS", "HUBS", "BILL", "CFLT",
    "TTD", "MGNI", "PUBM",
    
    # 中概股 (10)
    "BABA", "JD", "PDD", "BIDU", "NIO", "XPEV", "LI", "TCOM", "BILI", "TME",
    
    # 电信/通信 (5)
    "T", "VZ", "TMUS", "CHTR", "CMCSA",
    
    # 材料 (5)
    "LIN", "APD", "SHW", "FCX", "NEM",
    
    # REITs (5)
    "AMT", "PLD", "CCI", "EQIX", "DLR",
    
    # 汽车 (5)
    "GM", "F", "RIVN", "LCID", "TM"
]

# ============================================
# 历史分位数计算周期
# ============================================
HISTORY_YEARS = 5  # 使用5年历史数据计算分位数

# ============================================
# 技术指标参数
# ============================================
TECHNICAL_PARAMS = {
    "rsi_period": 14,
    "ma_short": 50,
    "ma_long": 200,
    "bollinger_period": 20,
    "bollinger_std": 2,
}

# ============================================
# 数据刷新频率 (分钟)
# ============================================
REFRESH_INTERVAL = 60  # 每60分钟刷新一次数据
