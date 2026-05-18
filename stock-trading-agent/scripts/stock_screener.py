#!/usr/bin/env python3
"""
🔍 A股选股粗筛器 - 纯Python，零LLM消耗
每日开盘前运行，从全市场筛选候选股票池

流程：
  1. 获取全市场活跃股（按成交量排序）
  2. 基础过滤（排除ST、市值、价格、换手率门槛）
  3. 技术面评分（均线、MACD、RSI、成交量）
  4. 板块/概念归类
  5. 输出候选池 Top 30

输出：候选股票列表 + 评分 + 所属板块
"""
import json, os, sys, re, urllib.request, urllib.parse
from datetime import datetime, date
from pathlib import Path
from typing import Optional

SCRIPTS_DIR = Path(os.path.expanduser("~/.hermes/skills/stock-trading-simulator/scripts"))
sys.path.insert(0, str(SCRIPTS_DIR))
os.chdir(str(SCRIPTS_DIR))

import importlib
spec = importlib.util.spec_from_file_location("stock_trader", SCRIPTS_DIR / "stock_trader.py")
st = importlib.util.module_from_spec(spec)
spec.loader.exec_module(st)

LOG_DIR = Path(os.path.expanduser("~/.hermes/stock-trading-logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 配置 ──────────────────────────────────────────────
MIN_MKTCAP = 5e8      # 最小总市值 5亿（剔除壳资源）
MIN_PRICE = 3.0       # 最低股价 3元（排除低价垃圾股）
MIN_TURNOVER = 0.3    # 最低换手率 0.3%
MAX_STOCKS = 500      # 取前多少只活跃股分析
TOP_N = 30            # 输出候选数量
MAX_PRICE = 500       # 最高股价（排除高价股，1手太贵）

# 排除的行业/板块关键词（ST股、退市整理等）
EXCLUDE_KEYWORDS = ["ST", "退市", "N", "C"]

# 扩展板块分类关键词（匹配股票名称和代码前缀）
SECTOR_KEYWORDS = {
    "AI/算力": ["人工智能", "算力", "AI", "大模型", "智能", "芯片", "半导体",
                "海光", "中科曙", "寒武纪", "景嘉微", "龙芯", "中芯", "华大"],
    "新能源": ["新能源", "锂电池", "光伏", "储能", "风电", "太阳能",
               "宁德", "比亚迪", "隆基", "通威", "阳光电源", "亿纬"],
    "消费电子": ["消费电子", "手机", "智能穿戴", "汽车电子", "立讯", "歌尔", "京东方"],
    "医药/医疗": ["医药", "医疗", "生物", "制药", "CXO", "创新药", "恒瑞", "迈瑞", "药明"],
    "金融/证券": ["银行", "证券", "保险", "券商", "金融", "平安", "招商", "中信"],
    "汽车": ["汽车", "整车", "新能源车", "无人驾驶", "汽配", "长城", "上汽"],
    "军工": ["军工", "航天", "航空", "国防", "中航", "沈飞"],
    "机器人": ["机器人", "人形机器人", "自动化", "埃斯顿", "汇川"],
    "通信/5G": ["通信", "5G", "光模块", "光纤", "中兴", "烽火"],
    "消费": ["白酒", "食品", "家电", "消费", "茅台", "五粮液", "美的", "格力"],
    "周期": ["钢铁", "煤炭", "有色", "化工", "石油", "万华", "紫金",
              "稀土", "锂", "铜", "铝"],
    "地产/基建": ["房地产", "基建", "建筑", "建材", "万科", "保利", "中国建筑"],
    "电力/能源": ["电力", "能源", "电网", "核电", "中石油", "中石化", "大唐"],
    "机械/制造": ["机械", "装备", "制造", "三一", "中联", "徐工"],
    "互联网/软件": ["互联网", "软件", "数据", "数字", "用友", "金山", "科大讯飞"],
}

# ── 数据获取 ──────────────────────────────────────────

# 市场数据中文字段映射（新浪API返回的key含义）
# trade=现价, changepercent=涨跌幅%, volume=成交量, amount=成交额
# per=市盈率, pb=市净率, mktcap=总市值, nmc=流通市值
# turnoverratio=换手率%

def fetch_active_stocks(max_count=MAX_STOCKS):
    """获取最活跃的股票列表（按成交量排序）"""
    all_stocks = []
    page = 1
    while len(all_stocks) < max_count:
        url = (f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
               f"Market_Center.getHQNodeData?page={page}&num=100"
               f"&sort=volume&asc=0&node=hs_a&symbol=&_s_r_a=init")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            raw = resp.read().decode("gbk")
            data = json.loads(raw)
            if not data:
                break
            all_stocks.extend(data)
            page += 1
        except Exception as e:
            print(f"  获取第{page}页失败: {e}", file=sys.stderr)
            break
    return all_stocks[:max_count]


def is_st_stock(name):
    """判断是否为ST股"""
    return any(kw in name for kw in EXCLUDE_KEYWORDS)


def safe_float(val, default=0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def classify_sector(name):
    """根据名称关键词判断所属板块"""
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in name.lower():
                return sector
    return "其他"


def screen_stocks():
    """主筛选流程"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M")
    
    log = []
    log.append(f"{'='*62}")
    log.append(f"🔍 选股粗筛 · {date_str}")
    log.append(f"{'='*62}")
    
    # 1. 获取活跃股
    log.append(f"\n📡 获取全市场活跃股...")
    stocks = fetch_active_stocks()
    log.append(f"   获取 {len(stocks)} 只股票")
    
    # 2. 基础过滤
    log.append(f"\n🔎 基础过滤...")
    passed = []
    excluded_map = {"ST/退市": 0, "市值过低": 0, "股价过低/过高": 0, "换手率过低": 0}
    
    for s in stocks:
        name = s.get("name", "")
        code = s.get("code", "")
        symbol = s.get("symbol", "")
        trade = safe_float(s.get("trade", 0))
        mktcap = safe_float(s.get("mktcap", 0)) * 10000  # 新浪单位是万元
        turnover = safe_float(s.get("turnoverratio", 0))
        
        # 排除ST
        if is_st_stock(name):
            excluded_map["ST/退市"] += 1
            continue
        
        # 市值过滤
        if mktcap < MIN_MKTCAP:
            excluded_map["市值过低"] += 1
            continue
        
        # 股价过滤
        if trade < MIN_PRICE or trade > MAX_PRICE:
            excluded_map["股价过低/过高"] += 1
            continue
        
        # 换手率过滤
        if turnover < MIN_TURNOVER:
            excluded_map["换手率过低"] += 1
            continue
        
        passed.append(s)
    
    for reason, count in excluded_map.items():
        if count > 0:
            log.append(f"   {reason}: 排除 {count} 只")
    log.append(f"   通过基础过滤: {len(passed)} 只")
    
    # 3. 逐一技术分析（取前80只分析，节省时间）
    log.append(f"\n📊 技术面分析...")
    scored = []
    analyze_count = min(len(passed), 80)
    
    for i, s in enumerate(passed[:analyze_count]):
        symbol = s.get("symbol", "")
        name = s.get("name", "")
        code = s.get("code", "")
        trade = safe_float(s.get("trade", 0))
        change_pct = safe_float(s.get("changepercent", 0))
        amount = safe_float(s.get("amount", 0))
        turnover = safe_float(s.get("turnoverratio", 0))
        mktcap = safe_float(s.get("mktcap", 0)) * 10000
        pe = safe_float(s.get("per", 0))
        
        # 行业分类
        sector = classify_sector(name)
        
        # 技术分析
        analysis = st.analyze_stock(symbol)
        tech_score = 0
        tech_reasons = []
        has_data = False
        
        if isinstance(analysis, dict) and "error" not in str(analysis):
            has_data = True
            trend_signals = analysis.get("trend_signals", [])
            signals_text = " ".join(trend_signals).lower()
            
            # 均线评分 (0~6分)
            ma_count = sum(1 for s in signals_text if "多头" in s)
            bear_count = sum(1 for s in signals_text if "空头" in s)
            ma_score = (ma_count - bear_count) * 2
            ma_score = max(-6, min(6, ma_score))
            tech_score += ma_score
            if ma_score > 0: tech_reasons.append(f"均线+{ma_score}")
            elif ma_score < 0: tech_reasons.append(f"均线{ma_score}")
            
            # MACD评分 (-3~3)
            macd_text = analysis.get("macd", "").lower()
            if "金叉" in macd_text: tech_score += 3; tech_reasons.append("金叉+3")
            elif "死叉" in macd_text: tech_score -= 3; tech_reasons.append("死叉-3")
            elif "多头" in macd_text: tech_score += 1; tech_reasons.append("MACD+1")
            elif "空头" in macd_text: tech_score -= 1; tech_reasons.append("MACD-1")
            
            # RSI评分 (-2~2)
            rsi_text = analysis.get("rsi", "").lower()
            rsi_match = re.search(r'rsi=(\d+\.?\d*)', rsi_text)
            if rsi_match:
                rsi_val = float(rsi_match.group(1))
                if rsi_val < 25: tech_score += 2; tech_reasons.append(f"RSI{rsi_val:.0f}超卖+2")
                elif rsi_val < 35: tech_score += 1; tech_reasons.append(f"RSI{rsi_val:.0f}偏低+1")
                elif rsi_val > 75: tech_score -= 2; tech_reasons.append(f"RSI{rsi_val:.0f}超买-2")
                elif rsi_val > 65: tech_score -= 1; tech_reasons.append(f"RSI{rsi_val:.0f}偏高-1")
        
        # 成交量评分 (0~2)
        vol_score = 0
        try:
            kline = st.get_history_kline(symbol, days=10)
            if isinstance(kline, dict):
                closes = kline.get("closes", [])
                volumes = kline.get("volumes", [])
                if len(volumes) >= 6:
                    avg_vol = sum(volumes[-6:-1]) / 5
                    cur_vol = volumes[-1] if volumes else 0
                    if cur_vol > avg_vol * 2: vol_score = 2; tech_reasons.append("放量2x+2")
                    elif cur_vol > avg_vol * 1.3: vol_score = 1; tech_reasons.append("放量+1")
        except:
            pass
        tech_score += vol_score
        
        # 综合评分
        # 技术(0-13) + 活跃度(0-3) = 基础分
        activity_score = min(3, turnover / 5)  # 换手率>5%给满分
        fundamental_score = 0
        if 0 < pe <= 50: fundamental_score += 1  # PE合理
        
        total_score = tech_score + activity_score + fundamental_score
        
        scored.append({
            "code": code,
            "symbol": symbol,
            "name": name,
            "price": trade,
            "change_pct": change_pct,
            "turnover": round(turnover, 2),
            "mktcap": round(mktcap, 0),
            "amount": round(amount, 0),
            "pe": round(pe, 1),
            "sector": sector,
            "tech_score": tech_score,
            "total_score": round(total_score, 1),
            "has_analysis": has_data,
            "tech_reasons": "; ".join(tech_reasons),
        })
        
        if (i + 1) % 20 == 0:
            log.append(f"   分析进度: {i+1}/{analyze_count}")
    
    log.append(f"   技术分析完成: {len(scored)} 只")
    
    # 4. 排序输出
    scored.sort(key=lambda x: x["total_score"], reverse=True)
    top = scored[:TOP_N]
    
    log.append(f"\n{'='*62}")
    log.append(f"🏆 候选股票池 Top {len(top)}")
    log.append(f"{'='*62}")
    log.append(f"{'代码':>10} {'名称':<10} {'现价':>8} {'涨幅':>7} {'换手':>6} {'评分':>5} {'板块':<12}")
    log.append(f"{'-'*62}")
    
    sector_count = {}
    for s in top:
        sector_count[s["sector"]] = sector_count.get(s["sector"], 0) + 1
        log.append(f"{s['symbol']:>10} {s['name']:<10} {s['price']:>8.2f} {s['change_pct']:>+6.2f}% "
                   f"{s['turnover']:>5.1f}% {s['total_score']:>5.1f} {s['sector']:<12}")
    
    # 板块分布
    log.append(f"\n📊 板块分布")
    for sec, cnt in sorted(sector_count.items(), key=lambda x: -x[1]):
        bar = "█" * cnt
        log.append(f"   {sec:<12} {bar} {cnt}只")
    
    log.append(f"\n{'='*62}")
    log.append(f"✅ 选股粗筛完成 · {date_str}")
    log.append(f"{'='*62}")
    
    # 保存候选池到JSON
    result = {
        "date": date.today().isoformat(),
        "generated_at": now.isoformat(),
        "total_analyzed": analyze_count,
        "candidates": [{
            "code": s["symbol"],
            "name": s["name"],
            "price": s["price"],
            "change_pct": s["change_pct"],
            "score": s["total_score"],
            "tech_score": s["tech_score"],
            "sector": s["sector"],
            "pe": s["pe"],
        } for s in top],
        "sector_distribution": sector_count,
    }
    
    pool_file = LOG_DIR / f"candidates_{date.today().isoformat()}.json"
    with open(pool_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    log.append(f"\n📁 候选池已保存: {pool_file}")
    
    return "\n".join(log)


def main():
    log = screen_stocks()
    log_file = LOG_DIR / f"screener_{date.today().isoformat()}.log"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(log)
    print(log)


if __name__ == "__main__":
    main()
