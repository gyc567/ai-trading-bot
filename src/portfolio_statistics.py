"""
投资组合统计模块 - 支持多币种交易统计
基于 trading_statistics.py 扩展
"""
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class PortfolioStatistics:
    """投资组合统计类 - 管理多币种交易历史和性能指标"""
    
    def __init__(self, stats_file='portfolio_stats.json', binance_client=None):
        self.stats_file = stats_file
        self.binance_client = binance_client  # 用于取消止损单
        self.start_time = None
        self.total_trades = 0
        self.win_trades = 0
        self.lose_trades = 0
        self.total_pnl = 0.0
        
        # 多币种支持
        self.coins = ['BNB', 'ETH', 'SOL', 'XRP', 'DOGE']
        self.current_positions = {coin: None for coin in self.coins}
        self.trade_history = []  # 所有交易历史
        self.trade_history_by_coin = {coin: [] for coin in self.coins}  # 按币种分类
        self.stop_loss_history = []  # 止损触发历史（保留7天）
        
        self.load()
    
    def load(self):
        """从文件加载统计数据"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.start_time = datetime.fromisoformat(data.get('start_time', datetime.now().isoformat()))
                    self.trade_history = data.get('trade_history', [])
                    self.total_trades = data.get('total_trades', 0)
                    self.win_trades = data.get('win_trades', 0)
                    self.lose_trades = data.get('lose_trades', 0)
                    self.total_pnl = data.get('total_pnl', 0.0)
                    self.current_positions = data.get('current_positions', {coin: None for coin in self.coins})
                    self.stop_loss_history = data.get('stop_loss_history', [])  # 加载止损历史
                    
                    # 重建按币种分类的历史
                    self.trade_history_by_coin = {coin: [] for coin in self.coins}
                    for trade in self.trade_history:
                        coin = trade.get('coin')
                        if coin in self.trade_history_by_coin:
                            self.trade_history_by_coin[coin].append(trade)
                    
                print(f"✅ 加载投资组合统计数据成功: {len(self.trade_history)}笔历史交易")
            except Exception as e:
                print(f"⚠️ 加载统计数据失败: {e}，将创建新的统计文件")
                self._initialize_new()
        else:
            self._initialize_new()
    
    def _initialize_new(self):
        """初始化新的统计数据"""
        self.start_time = datetime.now()
        self.trade_history = []
        self.total_trades = 0
        self.win_trades = 0
        self.lose_trades = 0
        self.total_pnl = 0.0
        self.current_positions = {coin: None for coin in self.coins}
        self.trade_history_by_coin = {coin: [] for coin in self.coins}
        self.save()
        print(f"✅ 初始化新的投资组合统计数据，启动时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def save(self):
        """保存统计数据到文件"""
        try:
            # 过滤止损历史，只保留最近7天
            cutoff_time = datetime.now() - timedelta(days=7)
            filtered_stop_losses = [
                sl for sl in self.stop_loss_history
                if datetime.fromisoformat(sl['timestamp']) > cutoff_time
            ]
            
            data = {
                'start_time': self.start_time.isoformat(),
                'trade_history': self.trade_history[-200:],  # 保留最近200笔
                'total_trades': self.total_trades,
                'win_trades': self.win_trades,
                'lose_trades': self.lose_trades,
                'total_pnl': self.total_pnl,
                'current_positions': self.current_positions,
                'stop_loss_history': filtered_stop_losses,  # 保存止损历史（7天）
                'last_update': datetime.now().isoformat()
            }
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ 保存统计数据失败: {e}")
    
    def record_position_entry(self, coin: str, side: str, entry_price: float, amount: float, stop_loss: float = 0, take_profit: float = 0, stop_order_id: int = 0):
        """记录开仓信息"""
        if coin not in self.coins:
            print(f"⚠️ 不支持的币种: {coin}")
            return
        
        self.current_positions[coin] = {
            'entry_time': datetime.now().isoformat(),
            'side': side,
            'entry_price': entry_price,
            'amount': amount,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'stop_order_id': stop_order_id  # 止损单ID
        }
        self.save()
        # 低价币种显示更多小数位
        decimals = 4 if coin in ['DOGE', 'XRP'] else 2
        sl_text = f" | 止损${stop_loss:.{decimals}f}" if stop_loss > 0 else ""
        tp_text = f" | 止盈${take_profit:.{decimals}f}" if take_profit > 0 else ""
        sl_status = "✅" if stop_order_id > 0 else ""
        print(f"📝 记录{coin}开仓: {side} @ ${entry_price:.{decimals}f}{sl_text}{sl_status}{tp_text}")
    
    def update_stop_loss_take_profit(self, coin: str, stop_loss: float = 0, take_profit: float = 0, stop_order_id: int = 0):
        """更新持仓的止损止盈"""
        if coin not in self.coins:
            print(f"⚠️ 不支持的币种: {coin}")
            return
        
        if coin not in self.current_positions or self.current_positions[coin] is None:
            print(f"⚠️ {coin}无持仓，跳过更新止损止盈")
            return
        
        old_sl = self.current_positions[coin].get('stop_loss', 0)
        old_tp = self.current_positions[coin].get('take_profit', 0)
        
        self.current_positions[coin]['stop_loss'] = stop_loss
        self.current_positions[coin]['take_profit'] = take_profit
        if stop_order_id > 0:
            self.current_positions[coin]['stop_order_id'] = stop_order_id
        self.save()
        
        # 只有变化时才打印
        if old_sl != stop_loss or old_tp != take_profit:
            # 低价币种显示更多小数位
            decimals = 4 if coin in ['DOGE', 'XRP'] else 2
            sl_text = f"${old_sl:.{decimals}f}→${stop_loss:.{decimals}f}" if stop_loss > 0 else f"${old_sl:.{decimals}f}→无"
            tp_text = f"${old_tp:.{decimals}f}→${take_profit:.{decimals}f}" if take_profit > 0 else f"${old_tp:.{decimals}f}→无"
            sl_status = "✅" if stop_order_id > 0 else ""
            print(f"📝 {coin}调整止损止盈: 止损{sl_text}{sl_status} | 止盈{tp_text}")
    
    def cancel_stop_loss_order(self, coin: str, symbol: str) -> bool:
        """取消止损单（容错处理）"""
        if not self.binance_client:
            print(f"⚠️ 未配置Binance客户端，无法取消止损单")
            return False
        
        if coin not in self.current_positions or self.current_positions[coin] is None:
            return False
        
        stop_order_id = self.current_positions[coin].get('stop_order_id', 0)
        if stop_order_id == 0:
            return False  # 没有止损单
        
        try:
            self.binance_client.futures_cancel_order(
                symbol=symbol,
                orderId=stop_order_id
            )
            print(f"🔴 已取消{coin}止损单 (订单ID: {stop_order_id})")
            return True
        except Exception as e:
            error_msg = str(e)
            # 订单已成交或已取消，不算错误
            if 'Unknown order' in error_msg or 'order does not exist' in error_msg.lower():
                print(f"ℹ️ {coin}止损单已不存在（可能已触发或已取消）")
                return True
            else:
                print(f"⚠️ 取消{coin}止损单失败: {error_msg[:100]}")
                return False
    
    def record_trade_exit(self, coin: str, exit_price: float, exit_reason: str = 'normal'):
        """记录平仓交易"""
        if coin not in self.coins:
            print(f"⚠️ 不支持的币种: {coin}")
            return
        
        if not self.current_positions.get(coin):
            print(f"⚠️ {coin}无持仓记录，无法记录平仓")
            return
        
        position = self.current_positions[coin]
        entry_time = datetime.fromisoformat(position['entry_time'])
        exit_time = datetime.now()
        duration = exit_time - entry_time
        duration_minutes = int(duration.total_seconds() / 60)
        
        # 计算盈亏
        entry_price = position['entry_price']
        amount = position['amount']
        side = position['side']
        
        if side == 'long':
            pnl = (exit_price - entry_price) * amount
        else:  # short
            pnl = (entry_price - exit_price) * amount
        
        pnl_percent = (pnl / (entry_price * amount)) * 100
        
        # 记录交易
        trade_record = {
            'coin': coin,
            'entry_time': position['entry_time'],
            'exit_time': exit_time.isoformat(),
            'side': side,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'amount': amount,
            'pnl': round(pnl, 2),
            'pnl_percent': round(pnl_percent, 2),
            'duration_minutes': duration_minutes,
            'exit_reason': exit_reason
        }
        
        # 添加到总历史和币种历史
        self.trade_history.append(trade_record)
        self.trade_history_by_coin[coin].append(trade_record)
        
        self.total_trades += 1
        self.total_pnl += pnl
        
        if pnl > 0:
            self.win_trades += 1
        else:
            self.lose_trades += 1
        
        # 清除该币种的持仓记录
        self.current_positions[coin] = None
        self.save()
        
        print(f"📝 记录{coin}交易: {side} | 盈亏 {pnl:+.2f} USDT ({pnl_percent:+.2f}%) | 持续 {duration_minutes}分钟")
    
    def get_runtime_info(self) -> Dict:
        """获取运行时长信息"""
        if not self.start_time:
            return {'minutes': 0, 'hours': 0, 'days': 0}
        
        runtime = datetime.now() - self.start_time
        total_minutes = int(runtime.total_seconds() / 60)
        total_hours = total_minutes // 60
        total_days = total_hours // 24
        
        return {
            'total_minutes': total_minutes,
            'total_hours': total_hours,
            'total_days': total_days,
            'hours_in_day': total_hours % 24,
            'minutes_in_hour': total_minutes % 60,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_coin_performance(self, coin: str) -> Dict:
        """获取单个币种的表现"""
        if coin not in self.coins:
            return {'total_trades': 0, 'win_trades': 0, 'lose_trades': 0, 'win_rate': 0, 'total_pnl': 0}
        
        coin_trades = self.trade_history_by_coin.get(coin, [])
        
        if not coin_trades:
            return {
                'total_trades': 0,
                'win_trades': 0,
                'lose_trades': 0,
                'win_rate': 0,
                'total_pnl': 0
            }
        
        wins = len([t for t in coin_trades if t['pnl'] > 0])
        losses = len(coin_trades) - wins
        win_rate = (wins / len(coin_trades)) * 100
        total_pnl = sum(t['pnl'] for t in coin_trades)
        
        return {
            'total_trades': len(coin_trades),
            'win_trades': wins,
            'lose_trades': losses,
            'win_rate': win_rate,
            'total_pnl': total_pnl
        }
    
    def get_recent_trades(self, count: int = 10) -> List[Dict]:
        """获取最近N笔交易"""
        return self.trade_history[-count:] if self.trade_history else []
    
    def get_trading_frequency(self, hours: int = 1) -> Dict:
        """获取最近N小时的交易频率"""
        if not self.trade_history:
            return {'trade_count': 0, 'frequency': 0.0, 'warning': ''}
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_trades = [
            t for t in self.trade_history
            if datetime.fromisoformat(t['exit_time']) > cutoff_time
        ]
        
        trade_count = len(recent_trades)
        frequency = trade_count / hours  # 笔/小时
        
        # 判断是否过度交易（每小时>2笔）
        warning = ''
        if frequency > 2:
            warning = '⚠️ 交易过于频繁！'
        elif frequency > 1.5:
            warning = '⚠️ 交易较频繁'
        
        return {
            'trade_count': trade_count,
            'frequency': frequency,
            'warning': warning
        }
    
    def get_win_rate(self, hours: int = 24) -> Dict:
        """获取最近N小时的胜率统计"""
        if not self.trade_history:
            return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'total_pnl': 0}
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_trades = [
            t for t in self.trade_history
            if datetime.fromisoformat(t['exit_time']) > cutoff_time
        ]
        
        if not recent_trades:
            return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'total_pnl': 0}
        
        wins = len([t for t in recent_trades if t['pnl'] > 0])
        losses = len(recent_trades) - wins
        win_rate = (wins / len(recent_trades)) * 100
        total_pnl = sum(t['pnl'] for t in recent_trades)
        
        return {
            'total': len(recent_trades),
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl': total_pnl
        }
    
    def get_position_durations(self) -> Dict[str, int]:
        """获取各币种当前持仓时长（分钟）"""
        durations = {}
        for coin, pos in self.current_positions.items():
            if pos:
                entry_time = datetime.fromisoformat(pos['entry_time'])
                duration = datetime.now() - entry_time
                durations[coin] = int(duration.total_seconds() / 60)
        return durations
    
    def calculate_sharpe_ratio(self, hours: int = None) -> float:
        """计算夏普比率
        
        夏普比率 = 平均收益率 / 收益率标准差
        对于交易系统，我们用每笔交易的收益率百分比来计算
        
        Args:
            hours: 如果为None，计算所有历史交易；如果指定，只计算最近N小时的交易
        """
        if not self.trade_history or len(self.trade_history) < 2:
            return 0.0
        
        # 如果指定了hours，只计算最近N小时的交易；否则计算所有历史交易
        if hours is not None:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            trades = [
                t for t in self.trade_history
                if datetime.fromisoformat(t['exit_time']) > cutoff_time
            ]
        else:
            # 计算所有历史交易
            trades = self.trade_history
        
        if len(trades) < 2:
            return 0.0
        
        # 提取每笔交易的收益率百分比
        returns = [t['pnl_percent'] for t in trades]
        
        # 计算平均收益率
        mean_return = sum(returns) / len(returns)
        
        # 计算收益率标准差
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5
        
        # 如果标准差为0，返回0（避免除以0）
        if std_dev == 0:
            return 0.0
        
        # 计算夏普比率
        sharpe_ratio = mean_return / std_dev
        
        return round(sharpe_ratio, 2)
    
    def generate_stats_text_for_ai(self) -> str:
        """生成给AI看的投资组合统计信息"""
        # 运行时长
        runtime = self.get_runtime_info()
        
        # 最近24小时统计
        recent_stats = self.get_win_rate(24)
        
        # 最近1小时交易频率
        freq_stats = self.get_trading_frequency(1)
        
        # 计算夏普比率（所有历史交易）
        sharpe_ratio = self.calculate_sharpe_ratio(hours=None)
        
        stats_text = f"""
    【系统运行统计】
    - 启动时间: {runtime['start_time']}
    - 已运行: {runtime['total_days']}天 {runtime['hours_in_day']}小时 {runtime['minutes_in_hour']}分钟
    
    【投资组合整体表现】
    - 历史总交易: {self.total_trades}笔 (胜{self.win_trades}负{self.lose_trades})
    - 历史总盈亏: {self.total_pnl:+.2f} USDT
    - 整体胜率: {(self.win_trades/self.total_trades*100) if self.total_trades > 0 else 0:.1f}%
    - 最近24小时: {recent_stats['total']}笔交易，胜率{recent_stats['win_rate']:.1f}%，盈亏{recent_stats['total_pnl']:+.2f} USDT
    - 夏普比率（所有历史交易）: {sharpe_ratio:.2f} {'✅' if sharpe_ratio > 0.7 else '⚠️' if sharpe_ratio > 0 else '❌'}
    
    ⏱️ 【交易频率监控】
    - 最近1小时: {freq_stats['trade_count']}笔交易 (频率: {freq_stats['frequency']:.2f}笔/小时) {freq_stats['warning']}
    - 建议标准: 每小时≤2笔 (监控6个币种)
    - 优秀节奏: 开仓后持有30-60分钟以上
    
    【各币种表现统计】"""
        
        # 各币种统计
        for coin in self.coins:
            perf = self.get_coin_performance(coin)
            if perf['total_trades'] > 0:
                stats_text += f"""
    {coin}: {perf['total_trades']}笔 | 胜率{perf['win_rate']:.1f}% | 盈亏{perf['total_pnl']:+.2f} USDT"""
            else:
                stats_text += f"""
    {coin}: 暂无交易记录"""
        
        # 最近10笔交易
        recent_trades = self.get_recent_trades(10)
        if recent_trades:
            stats_text += "\n\n    【最近10笔交易】"
            for i, trade in enumerate(reversed(recent_trades), 1):
                exit_time = datetime.fromisoformat(trade['exit_time'])
                time_str = exit_time.strftime('%m-%d %H:%M')
                side_emoji = "📈" if trade['side'] == 'long' else "📉"
                coin = trade.get('coin', '?')
                pnl_emoji = "✅" if trade['pnl'] > 0 else "❌"
                stats_text += f"""
    {i}. {time_str} | {coin} {side_emoji} | {pnl_emoji} {trade['pnl']:+.2f} USDT ({trade['pnl_percent']:+.2f}%)"""
        
        # 当前持仓时长
        durations = self.get_position_durations()
        if durations:
            stats_text += "\n\n    【当前持仓时长】"
            for coin, minutes in durations.items():
                hours = minutes // 60
                mins = minutes % 60
                stats_text += f"""
    {coin}: {hours}小时{mins}分钟"""
        
        return stats_text
    
    def get_summary(self) -> str:
        """获取统计摘要（用于日志）"""
        runtime = self.get_runtime_info()
        win_rate = (self.win_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        summary = f"""
{'='*60}
📊 投资组合统计摘要
{'='*60}
运行时长: {runtime['total_days']}天 {runtime['hours_in_day']}小时 {runtime['minutes_in_hour']}分钟
总交易数: {self.total_trades}笔
盈利交易: {self.win_trades}笔 ({win_rate:.1f}%)
亏损交易: {self.lose_trades}笔
累计盈亏: {self.total_pnl:+.2f} USDT

各币种表现:"""
        
        for coin in self.coins:
            perf = self.get_coin_performance(coin)
            if perf['total_trades'] > 0:
                summary += f"""
  {coin}: {perf['total_trades']}笔 | 胜率{perf['win_rate']:.1f}% | 盈亏{perf['total_pnl']:+.2f} USDT"""
        
        summary += f"\n{'='*60}"
        return summary
    
    def record_stop_loss_triggered(self, coin: str, side: str, entry_price: float, stop_price: float, 
                                   amount: float, trigger_time: datetime, pnl: float, entry_time: datetime = None):
        """记录止损单触发事件"""
        # 计算持仓时长
        if entry_time is None:
            duration_minutes = 0
        else:
            duration_minutes = int((trigger_time - entry_time).total_seconds() / 60)
        
        record = {
            'timestamp': trigger_time.isoformat(),
            'coin': coin,
            'side': side,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'amount': amount,
            'pnl': round(pnl, 2),
            'duration_minutes': duration_minutes
        }
        
        self.stop_loss_history.append(record)
        
        # 打印日志（低价币种显示更多小数位）
        decimals = 4 if coin in ['DOGE', 'XRP'] else 2
        print(f"📋 止损触发记录已保存: {coin} {side.upper()} | "
              f"开仓${entry_price:.{decimals}f} → 止损${stop_price:.{decimals}f} | "
              f"盈亏{pnl:+.2f} USDT | 持仓{duration_minutes}分钟")
        
        self.save()
    
    def get_recent_stop_losses(self, minutes: int = 30) -> List[Dict]:
        """获取最近N分钟内的止损触发记录"""
        if not self.stop_loss_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent = [
            sl for sl in self.stop_loss_history
            if datetime.fromisoformat(sl['timestamp']) > cutoff_time
        ]
        
        # 按时间倒序排列（最新的在前）
        recent.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return recent

