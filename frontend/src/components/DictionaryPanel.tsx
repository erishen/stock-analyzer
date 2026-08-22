import { FC, useMemo, useState } from 'react'

interface DictEntry {
  term: string
  cat: string
  desc: string
}

const CATS = ['全部', '基础概念', '交易规则', '技术指标', '大盘行情', '持仓策略', '组合风控']

const DICT: DictEntry[] = [
  // ---- 基础概念 ----
  { term: '股票', cat: '基础概念', desc: '股份公司发行的所有权凭证。持有即成为公司股东，可从股价上涨和分红中获利，也要承担下跌风险。' },
  { term: 'A股', cat: '基础概念', desc: '人民币普通股，在中国内地交易所（上交所、深交所、北交所）上市交易，是普通投资者最常参与的股票。' },
  { term: '一手', cat: '基础概念', desc: 'A股买卖的最小单位，1手=100股。买入必须是100股的整数倍。' },
  { term: '市值 / 总市值', cat: '基础概念', desc: '公司当前的"身价"，=股价×总股本。市值大代表公司规模大，大盘股波动相对温和。' },
  { term: '流通市值', cat: '基础概念', desc: '仅计算可在市场上自由交易的股份对应的市值。流通盘越大，越难被少数资金拉抬。' },
  { term: '复权', cat: '基础概念', desc: '公司分红或送转会导致股价跳空，复权就是把这些影响"抹平"以便连续观察真实涨跌。前复权以当前价为准，后复权以最早价为基准。' },

  // ---- 交易规则 ----
  { term: 'T+1 交易', cat: '交易规则', desc: '当天买入的股票，最早要第二天才能卖出（A股现行规则）。每天最多实现一次"买-卖"的换手。' },
  { term: '集合竞价', cat: '交易规则', desc: '开盘（9:15-9:25）和收盘（14:57-15:00）的一段时间，买卖申报集中撮合，按统一价格成交，决定开盘/收盘价。' },
  { term: '连续竞价', cat: '交易规则', desc: '盘中（9:30-11:30、13:00-14:57）连续按价格优先、时间优先的原则逐笔撮合成交。' },
  { term: '涨停 / 跌停', cat: '交易规则', desc: '主板单日最大涨跌幅限制：普通股票±10%，创业板/科创板±20%，ST股±5%。触及后不再接受更高/更低报价。' },
  { term: '涨跌幅', cat: '交易规则', desc: '股价相对昨日收盘价的变动幅度，=(今收-昨收)/昨收×100%。是观察个股强弱最基本的数据。' },
  { term: '停牌', cat: '交易规则', desc: '因重大事项或异常波动，交易所暂停该股票的买卖。停牌期间无法交易。' },
  { term: '除权除息', cat: '交易规则', desc: '分红送配后，为保持总价值不变对股价做技术性下调（股票代码前会标 XD、XR、DR）。' },
  { term: 'IPO / 打新', cat: '交易规则', desc: 'IPO 是公司首次公开发行股票上市；打新是投资者申购新股，中签后以发行价买入，通常上市初期有溢价。' },

  // ---- 技术指标 ----
  { term: 'K线（蜡烛图）', cat: '技术指标', desc: '用一根柱体记录一段时间（日/周/月）的开盘、最高、最低、收盘四价。红/阳线（收>开）代表上涨，绿/阴线代表下跌。' },
  { term: '均线 MA', cat: '技术指标', desc: '一段时间的平均收盘价连线。MA5/MA10 是短期线，MA20/MA60 是中期线。价格在均线上方偏强，下方偏弱；短期线在长期线上方为"多头排列"。' },
  { term: 'MACD', cat: '技术指标', desc: '基于两条均线差研判趋势的指标。快线(白线)在慢线(黄线)上方、柱状图为红时为多头趋势，反之空头。金叉（快线上穿慢线）常被视作买入信号。' },
  { term: 'RSI 强弱', cat: '技术指标', desc: '取0-100的涨跌力量比值，>70超买（过热小心回调）、<30超卖（超跌可能反弹）、50附近中性。' },
  { term: 'KDJ 随机指标', cat: '技术指标', desc: '衡量短期价格相对位置的摆动指标。K/D 值>80超买、<20超卖，金叉/死叉给出短线买卖参考。' },
  { term: 'BOLL 布林带', cat: '技术指标', desc: '由中轨（20日均线）加上/下轨构成的价格通道。价格触及上下轨提示超买/超卖，通道收窄往往预示变盘。' },
  { term: '成交量 / 量能', cat: '技术指标', desc: '一段时间内成交的股数或金额，反映参与热度。"量价齐升"健康，"放量滞涨"要警惕。' },
  { term: '换手率', cat: '技术指标', desc: '当天成交量占流通股本的比例，越高代表交投越活跃。是妖股、热点股的重要观察指标。' },
  { term: '振幅', cat: '技术指标', desc: '(最高价-最低价)/昨收的百分比，反映单日价格摆动幅度，衡量当日波动剧烈程度。' },
  { term: 'CCI 顺势指标', cat: '技术指标', desc: '衡量股价是否超出正常波动区间。>100显强势、<-100偏弱，用于捕捉偏离常态的变化。' },
  { term: 'ATR 真实波幅', cat: '技术指标', desc: '平均真实波幅，衡量股价单日波动幅度的大小。值越大波动越剧烈，常用于据此设定止损幅度。' },
  { term: '市场广度', cat: '技术指标', desc: '当天上涨股票占全市场的比例(%)。>60%为普涨，<50%说明赚钱效应差，反映"大盘指数的含金量"。' },

  // ---- 大盘行情 ----
  { term: '指数', cat: '大盘行情', desc: '对一群股票价格加权后得出的综合值，用来代表一类市场整体水平。' },
  { term: '上证指数 / 深证成指 / 创业板指', cat: '大盘行情', desc: '分别代表沪市、深市主板、创业板整体走势的三大指数，是A股行情的风向标。' },
  { term: '牛市 / 熊市 / 震荡市', cat: '大盘行情', desc: '整体趋势性上涨叫牛市（乐观），持续下跌叫熊市（悲观），长期横盘区间波动叫震荡市。' },
  { term: '红涨绿跌', cat: '大盘行情', desc: 'A股约定俗成的颜色规则：红色代表上涨，绿色代表下跌（本系统统一此配色）。' },
  { term: '普涨 / 普跌 / 结构行情', cat: '大盘行情', desc: '指数涨而大部分股票也涨叫普涨，反之普跌；只有部分板块涨、其他跌叫结构性行情（结构性机会）。' },
  { term: '板块 / 行业轮动', cat: '大盘行情', desc: '资金在不同行业板块之间流动，热点从一个板块切换到另一个板块的现象。' },
  { term: '大盘择时', cat: '大盘行情', desc: '通过整体强弱指标判断当前处于牛市/震荡/熊市，从而指导仓位轻重，决定"敢不敢重仓"。' },

  // ---- 持仓策略 ----
  { term: '多头 / 空头', cat: '持仓策略', desc: '看涨并持有/买入的一方叫多头，看跌或卖出的一方叫空头。"做多"=买入等待上涨。' },
  { term: '建仓 / 加仓 / 减仓', cat: '持仓策略', desc: '建仓=初次买入建立仓位；加仓=在上涨或回踩中继续买入；减仓=卖出部分降低持仓。' },
  { term: '满仓 / 空仓', cat: '持仓策略', desc: '全部资金都买了股票叫满仓；手上没有股票、全是现金叫空仓/清仓。' },
  { term: '止损 / 止盈', cat: '持仓策略', desc: '为控制亏损在跌破设定价位时卖出（止损）；为锁定利润在达到目标价位时卖出（止盈）。' },
  { term: '仓位管理/仓位', cat: '持仓策略', desc: '你投入股票的资金占总资金的比例，以及各只股票的占比。仓位决定风险敞口大小。' },
  { term: '波段', cat: '持仓策略', desc: '在震荡行情中低买高卖、吃一段区间利润的操作方式，区别于长期持有或短线打板。' },
  { term: '抄底 / 追高', cat: '持仓策略', desc: '抄底=在低位接盘赌反弹；追高=在高位买入强势股。两者都有风险，需配合止损。' },
  { term: '打板', cat: '持仓策略', desc: '在涨停瞬间排队买入，博取次日继续涨停（连板）的短线激进打法，风险极高。' },
  { term: '价值投资', cat: '持仓策略', desc: '基于公司基本面，认为股价终会回归其内在价值而长期持有，重视业绩与估值而非短期波动。' },

  // ---- 组合风控 ----
  { term: '组合 / 持仓', cat: '组合风控', desc: '你手里所有股票构成的整体。看组合不能只看单只，要关注整体盈亏与风险集中度。' },
  { term: '分散化', cat: '组合风控', desc: '把资金放进多只不同行业、相关性低的股票，避免"鸡蛋全放一个篮子"的集中风险。' },
  { term: '相关性', cat: '组合风控', desc: '两只股票同涨同跌的程度，取值-1到1。相关性越高，分散效果越差；越低越能对冲个股风险。' },
  { term: '最大回撤', cat: '组合风控', desc: '从阶段性高点回落的幅度中最大的那个"，衡量策略最坏能亏多少，越小越稳健。' },
  { term: '波动率', cat: '组合风控', desc: '收益率的标准差，衡量价格晃动的剧烈程度。只看振幅、不分方向，越高风险越大。' },
  { term: '夏普比率', cat: '组合风控', desc: '(收益-无风险利率)/波动率，衡量"每承担一单位风险换来多少超额收益"，越高性价比越好。' },
  { term: '年化收益', cat: '组合风控', desc: '把一段时间收益率折算成"每年"的水平，便于不同周期业绩互相比较。' },
  { term: '胜率', cat: '组合风控', desc: '盈利交易笔数占总交易笔数的比例。胜率不是一切，还要配合盈亏比看总盈利。' },
  { term: '盈亏比', cat: '组合风控', desc: '平均每笔盈利与平均每笔亏损的比值。越高，即使胜率不高也能整体赚钱。' },
]

export const DictionaryPanel: FC = () => {
  const [search, setSearch] = useState('')
  const [cat, setCat] = useState('全部')

  const filtered = useMemo(() => {
    const kw = search.trim().toLowerCase()
    return DICT.filter((d) => {
      if (cat !== '全部' && d.cat !== cat) return false
      if (!kw) return true
      return d.term.toLowerCase().includes(kw) || d.desc.toLowerCase().includes(kw)
    })
  }, [search, cat])

  const grouped = useMemo(() => {
    if (search.trim()) {
      return [{ cat: '搜索结果', items: filtered }]
    }
    const map = new Map<string, DictEntry[]>()
    for (const d of filtered) {
      if (!map.has(d.cat)) map.set(d.cat, [])
      map.get(d.cat)!.push(d)
    }
    return [...map.entries()].map(([c, items]) => ({ cat: c, items }))
  }, [filtered, search])

  return (
    <div className="bg-white rounded-lg p-5 shadow-sm">
      <h2 className="text-xl font-semibold mb-1">📖 术语字典</h2>
      <p className="text-gray-500 text-sm mb-4">股市常用术语的通俗解释，支持搜索与分类浏览</p>

      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="🔍 输入术语搜索，如 RSI、止损、市值..."
          className="flex-1 px-4 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
        />
        <div className="flex flex-wrap gap-2">
          {CATS.map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={`px-3 py-1.5 rounded-full text-xs transition ${
                cat === c ? 'bg-violet-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="text-xs text-gray-400 mb-4">共 {filtered.length} 个术语</div>

      {filtered.length === 0 && (
        <div className="py-10 text-center text-gray-400 text-sm">没有找到相关术语，换个关键词试试</div>
      )}

      {grouped.map((g) => (
        <div key={g.cat} className="mb-5">
          <h3 className="font-semibold text-sm text-violet-700 mb-2">{g.cat}</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {g.items.map((d) => (
              <div key={d.term} className="border border-gray-100 rounded-lg p-3 hover:shadow-sm transition">
                <div className="font-medium text-sm mb-1">{d.term}</div>
                <p className="text-sm text-gray-500 leading-relaxed">{d.desc}</p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}