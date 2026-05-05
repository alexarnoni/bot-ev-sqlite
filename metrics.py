"""
Sistema de Métricas - Tracking de P50/P95/P99 para latência e performance
"""
import asyncio
import functools
import time
import statistics
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from collections import deque, defaultdict
import threading
import json
import os
from contextlib import contextmanager

class MetricsCollector:
    """Coletor de métricas com tracking de percentis"""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.lock = threading.Lock()
        
        # Armazenamento de métricas por categoria
        self.metrics = defaultdict(lambda: deque(maxlen=max_samples))
        
        # Contadores
        self.counters = defaultdict(int)
        
        # Timestamps para cálculos de taxa
        self.last_reset = time.time()
        
        # Métricas específicas do bot
        self.bot_metrics = {
            'api_requests': deque(maxlen=max_samples),
            'scan_duration': deque(maxlen=max_samples),
            'alert_processing': deque(maxlen=max_samples),
            'database_queries': deque(maxlen=max_samples),
            'cache_hits': deque(maxlen=max_samples),
            'cache_misses': deque(maxlen=max_samples),
        }
    
    def record_latency(self, category: str, duration: float, metadata: Optional[Dict] = None):
        """Registra latência para uma categoria específica"""
        with self.lock:
            self.metrics[category].append({
                'duration': duration,
                'timestamp': time.time(),
                'metadata': metadata or {}
            })
    
    def increment_counter(self, counter_name: str, value: int = 1):
        """Incrementa um contador"""
        with self.lock:
            self.counters[counter_name] += value
    
    def record_bot_metric(self, metric_type: str, value: float, metadata: Optional[Dict] = None):
        """Registra métrica específica do bot"""
        with self.lock:
            if metric_type in self.bot_metrics:
                self.bot_metrics[metric_type].append({
                    'value': value,
                    'timestamp': time.time(),
                    'metadata': metadata or {}
                })
    
    def get_percentiles(self, category: str, percentiles: List[float] = [50, 95, 99]) -> Dict[str, float]:
        """Calcula percentis para uma categoria"""
        with self.lock:
            if category not in self.metrics or not self.metrics[category]:
                return {}
            
            durations = [m['duration'] for m in self.metrics[category]]
            durations.sort()
            
            result = {}
            for p in percentiles:
                if durations:
                    index = int((p / 100) * (len(durations) - 1))
                    result[f'p{p}'] = durations[index]
            
            return result
    
    def get_bot_percentiles(self, metric_type: str, percentiles: List[float] = [50, 95, 99]) -> Dict[str, float]:
        """Calcula percentis para métricas específicas do bot"""
        with self.lock:
            if metric_type not in self.bot_metrics or not self.bot_metrics[metric_type]:
                return {}
            
            values = [m['value'] for m in self.bot_metrics[metric_type]]
            values.sort()
            
            result = {}
            for p in percentiles:
                if values:
                    index = int((p / 100) * (len(values) - 1))
                    result[f'p{p}'] = values[index]
            
            return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo completo das métricas"""
        with self.lock:
            summary = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'counters': dict(self.counters),
                'latency_metrics': {},
                'bot_metrics': {},
                'rates': self._calculate_rates()
            }
            
            # Métricas de latência por categoria
            for category in self.metrics:
                if self.metrics[category]:
                    durations = [m['duration'] for m in self.metrics[category]]
                    summary['latency_metrics'][category] = {
                        'count': len(durations),
                        'min': min(durations),
                        'max': max(durations),
                        'avg': statistics.mean(durations),
                        'median': statistics.median(durations),
                        'percentiles': self.get_percentiles(category)
                    }
            
            # Métricas específicas do bot
            for metric_type in self.bot_metrics:
                if self.bot_metrics[metric_type]:
                    values = [m['value'] for m in self.bot_metrics[metric_type]]
                    summary['bot_metrics'][metric_type] = {
                        'count': len(values),
                        'min': min(values),
                        'max': max(values),
                        'avg': statistics.mean(values),
                        'median': statistics.median(values),
                        'percentiles': self.get_bot_percentiles(metric_type)
                    }
            
            return summary
    
    def _calculate_rates(self) -> Dict[str, float]:
        """Calcula taxas por segundo"""
        current_time = time.time()
        time_diff = current_time - self.last_reset
        
        rates = {}
        for counter_name, count in self.counters.items():
            rates[f'{counter_name}_per_second'] = count / time_diff if time_diff > 0 else 0
        
        return rates
    
    def reset(self):
        """Reseta todas as métricas"""
        with self.lock:
            self.metrics.clear()
            self.counters.clear()
            for metric_type in self.bot_metrics:
                self.bot_metrics[metric_type].clear()
            self.last_reset = time.time()
    
    def save_to_file(self, filepath: str):
        """Salva métricas em arquivo JSON"""
        summary = self.get_summary()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    
    @contextmanager
    def time_operation(self, category: str, metadata: Optional[Dict] = None):
        """Context manager para medir tempo de operações"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_latency(category, duration, metadata)


# Instância global do coletor
_metrics_collector: Optional[MetricsCollector] = None

def get_metrics_collector() -> MetricsCollector:
    """Retorna instância global do coletor de métricas"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

def record_api_request(duration: float, status_code: int, endpoint: str):
    """Registra métrica de requisição à API"""
    collector = get_metrics_collector()
    collector.record_latency('api_request', duration, {
        'status_code': status_code,
        'endpoint': endpoint
    })
    collector.increment_counter('api_requests_total')
    if status_code >= 400:
        collector.increment_counter('api_errors_total')

def record_scan_duration(duration: float, events_found: int, alerts_sent: int):
    """Registra métrica de duração do scan"""
    collector = get_metrics_collector()
    collector.record_latency('scan_duration', duration, {
        'events_found': events_found,
        'alerts_sent': alerts_sent
    })
    collector.record_bot_metric('scan_duration', duration, {
        'events_found': events_found,
        'alerts_sent': alerts_sent
    })

def record_database_query(duration: float, query_type: str, rows_affected: int = 0):
    """Registra métrica de query do banco"""
    collector = get_metrics_collector()
    collector.record_latency('database_query', duration, {
        'query_type': query_type,
        'rows_affected': rows_affected
    })
    collector.record_bot_metric('database_queries', duration, {
        'query_type': query_type,
        'rows_affected': rows_affected
    })

def record_cache_operation(hit: bool, duration: float, cache_type: str):
    """Registra métrica de operação de cache"""
    collector = get_metrics_collector()
    collector.record_latency('cache_operation', duration, {
        'hit': hit,
        'cache_type': cache_type
    })
    
    if hit:
        collector.record_bot_metric('cache_hits', duration, {'cache_type': cache_type})
        collector.increment_counter('cache_hits_total')
    else:
        collector.record_bot_metric('cache_misses', duration, {'cache_type': cache_type})
        collector.increment_counter('cache_misses_total')

def record_alert_processing(duration: float, alerts_count: int, success: bool):
    """Registra métrica de processamento de alertas"""
    collector = get_metrics_collector()
    collector.record_latency('alert_processing', duration, {
        'alerts_count': alerts_count,
        'success': success
    })
    collector.record_bot_metric('alert_processing', duration, {
        'alerts_count': alerts_count,
        'success': success
    })
    
    if success:
        collector.increment_counter('alerts_sent_total', alerts_count)
    else:
        collector.increment_counter('alerts_failed_total', alerts_count)

def get_metrics_summary() -> Dict[str, Any]:
    """Retorna resumo das métricas"""
    return get_metrics_collector().get_summary()

def reset_metrics():
    """Reseta todas as métricas"""
    get_metrics_collector().reset()

def save_metrics(filepath: str = None):
    """Salva métricas em arquivo"""
    if filepath is None:
        filepath = f"logs/metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    get_metrics_collector().save_to_file(filepath)

# Decorator para medir tempo de funções
def measure_time(category: str, metadata: Optional[Dict] = None):
    """Decorator para medir tempo de execução de funções"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                collector = get_metrics_collector()
                with collector.time_operation(category, metadata):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                collector = get_metrics_collector()
                with collector.time_operation(category, metadata):
                    return func(*args, **kwargs)
            return sync_wrapper
    return decorator
