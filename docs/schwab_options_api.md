# Schwab API - Comprehensive Options Data Collection Guide

## Overview

This document outlines the complete methodology for collecting options data using the Schwab API, based on the official API documentation and your existing market data streaming application.

## Table of Contents
1. [API Authentication](#api-authentication)
2. [Options Chain Data Collection](#options-chain-data-collection)
3. [Real-Time Options Streaming](#real-time-options-streaming)
4. [Supporting Market Data APIs](#supporting-market-data-apis)
5. [Implementation Strategies](#implementation-strategies)
6. [Data Processing Workflows](#data-processing-workflows)
7. [Error Handling & Rate Limits](#error-handling--rate-limits)

---

## API Authentication

### OAuth 2.0 Setup
```python
# Required credentials from https://developer.schwab.com/
SCHWAB_APP_KEY = "your_app_key_here"
SCHWAB_APP_SECRET = "your_app_secret_here"
CALLBACK_URL = "https://127.0.0.1"  # Required exact format
```

### Authentication Flow
1. **Authorization URL**: Direct user to Schwab OAuth page
2. **Callback Handling**: Capture authorization code from redirect
3. **Token Exchange**: Convert code to access/refresh tokens
4. **Token Management**: Automatic refresh for continuous operation

---

## Options Chain Data Collection

### 1. Option Chains API (`GET /chains`)

**Primary endpoint for comprehensive options data collection.**

#### Request Parameters
```python
{
    "symbol": "SPY",                    # Required: Underlying symbol
    "contractType": "ALL",              # ALL, CALL, PUT
    "strikeCount": 20,                  # Number of strikes around current price
    "includeQuotes": "TRUE",            # Include real-time quotes
    "strategy": "SINGLE",               # SINGLE, ANALYTICAL, COVERED, etc.
    "interval": 1,                      # Strike price intervals
    "strike": 420.0,                    # Specific strike (optional)
    "range": "ALL",                     # ALL, ITM, OTM, SAK, SBK, SNK
    "fromDate": "2024-12-01",          # Start date (YYYY-MM-DD)
    "toDate": "2025-01-31",            # End date (YYYY-MM-DD)
    "volatility": 0.25,                # Implied volatility filter
    "underlyingPrice": 420.50,         # Current underlying price
    "interestRate": 0.05,              # Risk-free rate
    "daysToExpiration": 30,            # Days to expiration filter
    "expMonth": "ALL"                  # Expiration month filter
}
```

#### Response Structure
```json
{
    "symbol": "SPY",
    "status": "SUCCESS",
    "underlying": {
        "ask": 420.55,
        "bid": 420.50,
        "change": 2.15,
        "close": 418.35,
        "delayed": false,
        "description": "SPDR S&P 500 ETF Trust",
        "exchangeName": "ARCX",
        "fiftyTwoWeekHigh": 475.50,
        "fiftyTwoWeekLow": 362.25,
        "highPrice": 421.00,
        "last": 420.52,
        "lowPrice": 418.80,
        "mark": 420.525,
        "markChange": 2.175,
        "markPercentChange": 0.52,
        "openPrice": 419.00,
        "percentChange": 0.514,
        "quoteTime": 1703188800000,
        "symbol": "SPY",
        "totalVolume": 45678912,
        "tradeTime": 1703188800000
    },
    "strategy": "SINGLE",
    "interval": 1.0,
    "isDelayed": false,
    "isIndex": false,
    "daysToExpiration": 14.0,
    "interestRate": 0.0525,
    "underlyingPrice": 420.52,
    "volatility": 0.2156,
    "callExpDateMap": {
        "2024-12-15:14": {
            "415.0": [{
                "putCall": "CALL",
                "symbol": "SPY_121524C415",
                "description": "SPY Dec 15 2024 $415 Call",
                "exchangeName": "OPRA",
                "bid": 6.25,
                "ask": 6.35,
                "last": 6.30,
                "mark": 6.30,
                "bidSize": 45,
                "askSize": 38,
                "bidAskSize": "45X38",
                "lastSize": 12,
                "highPrice": 6.45,
                "lowPrice": 5.95,
                "openPrice": 6.15,
                "closePrice": 4.85,
                "totalVolume": 1247,
                "tradeDate": null,
                "tradeTimeInLong": 1703188800000,
                "quoteTimeInLong": 1703188800000,
                "netChange": 1.45,
                "volatility": 18.752,
                "delta": 0.7234,
                "gamma": 0.0892,
                "theta": -0.1567,
                "vega": 0.0234,
                "rho": 0.0456,
                "openInterest": 12847,
                "timeValue": 0.78,
                "theoreticalOptionValue": 6.28,
                "theoreticalVolatility": 18.75,
                "optionDeliverablesList": null,
                "strikePrice": 415.0,
                "expirationDate": 1734220800000,
                "daysToExpiration": 14,
                "expirationType": "R",
                "lastTradingDay": 1734220800000,
                "multiplier": 100.0,
                "settlementType": " ",
                "deliverableNote": "",
                "isIndexOption": null,
                "percentChange": 29.90,
                "markChange": 1.45,
                "markPercentChange": 29.90,
                "intrinsicValue": 5.52,
                "pennyPilot": true,
                "nonStandard": false,
                "inTheMoney": true
            }]
        }
    },
    "putExpDateMap": {
        "2024-12-15:14": {
            "425.0": [{
                "putCall": "PUT",
                "symbol": "SPY_121524P425",
                "description": "SPY Dec 15 2024 $425 Put",
                "exchangeName": "OPRA",
                "bid": 5.15,
                "ask": 5.25,
                "last": 5.20,
                "mark": 5.20,
                "bidSize": 67,
                "askSize": 42,
                "bidAskSize": "67X42",
                "lastSize": 8,
                "highPrice": 5.45,
                "lowPrice": 4.95,
                "openPrice": 5.25,
                "closePrice": 3.85,
                "totalVolume": 892,
                "tradeDate": null,
                "tradeTimeInLong": 1703188800000,
                "quoteTimeInLong": 1703188800000,
                "netChange": 1.35,
                "volatility": 19.234,
                "delta": -0.2766,
                "gamma": 0.0892,
                "theta": -0.1234,
                "vega": 0.0198,
                "rho": -0.0234,
                "openInterest": 8934,
                "timeValue": 0.72,
                "theoreticalOptionValue": 5.18,
                "theoreticalVolatility": 19.23,
                "optionDeliverablesList": null,
                "strikePrice": 425.0,
                "expirationDate": 1734220800000,
                "daysToExpiration": 14,
                "expirationType": "R",
                "lastTradingDay": 1734220800000,
                "multiplier": 100.0,
                "settlementType": " ",
                "deliverableNote": "",
                "isIndexOption": null,
                "percentChange": 35.06,
                "markChange": 1.35,
                "markPercentChange": 35.06,
                "intrinsicValue": 4.48,
                "pennyPilot": true,
                "nonStandard": false,
                "inTheMoney": true
            }]
        }
    }
}
```

### 2. Option Expiration Chain API (`GET /expirationchain`)

**Get available expiration dates for options planning.**

#### Request Parameters
```python
{
    "symbol": "SPY"  # Required: Underlying symbol
}
```

#### Response Structure
```json
{
    "status": "SUCCESS",
    "expirationList": [
        {
            "expirationDate": "2024-12-06",
            "daysToExpiration": 2,
            "expirationType": "W",  # W=Weekly, S=Standard, Q=Quarterly
            "standard": false
        },
        {
            "expirationDate": "2024-12-13",
            "daysToExpiration": 9,
            "expirationType": "W",
            "standard": false
        },
        {
            "expirationDate": "2024-12-20",
            "daysToExpiration": 16,
            "expirationType": "S",
            "standard": true
        }
    ]
}
```

---

## Real-Time Options Streaming

### WebSocket Streaming API

**Access real-time options data through WebSocket connections.**

#### Available Services
1. **LEVELONE_OPTIONS** - Real-time Level 1 options quotes
2. **OPTIONS_BOOK** - Level 2 order book data

#### LEVELONE_OPTIONS Fields
```python
OPTION_FIELDS = {
    0: "Symbol",                    # Option symbol
    1: "Description",              # Option description
    2: "Bid Price",                # Current bid
    3: "Ask Price",                # Current ask
    4: "Last Price",               # Last trade price
    5: "High Price",               # Day's high
    6: "Low Price",                # Day's low
    7: "Close Price",              # Previous close
    8: "Total Volume",             # Day's volume
    9: "Open Interest",            # Open interest
    10: "Volatility",              # Implied volatility
    11: "Money Intrinsic Value",   # Intrinsic value
    18: "Last Size",               # Last trade size
    19: "Net Change",              # Price change
    20: "Strike Price",            # Strike price
    28: "Delta",                   # Option delta
    29: "Gamma",                   # Option gamma
    30: "Theta",                   # Option theta
    31: "Vega",                    # Option vega
    32: "Rho",                     # Option rho
    37: "Mark Price",              # Mark price
    42: "Net Percent Change"       # Percent change
}
```

#### Streaming Subscription Example
```python
# Login to streaming service
login_request = {
    "requests": [{
        "service": "ADMIN",
        "command": "LOGIN",
        "requestid": "1",
        "SchwabClientCustomerId": customer_id,
        "SchwabClientCorrelId": correlation_id,
        "parameters": {
            "Authorization": access_token,
            "SchwabClientChannel": channel,
            "SchwabClientFunctionId": function_id
        }
    }]
}

# Subscribe to options
options_request = {
    "requests": [{
        "service": "LEVELONE_OPTIONS",
        "command": "SUBS",
        "requestid": "2",
        "SchwabClientCustomerId": customer_id,
        "SchwabClientCorrelId": correlation_id,
        "parameters": {
            "keys": "SPY_121524C420,SPY_121524P420",  # Option symbols
            "fields": "0,1,2,3,4,8,10,19,20,28,37"   # Selected fields
        }
    }]
}
```

---

## Supporting Market Data APIs

### 1. Quotes API (`GET /quotes`)

**Get real-time quotes for underlying securities.**

```python
# Single quote
GET /marketdata/v1/SPY/quotes

# Multiple quotes  
GET /marketdata/v1/quotes?symbols=SPY,QQQ,IWM&fields=quote,fundamental
```

### 2. Price History API (`GET /pricehistory`)

**Historical data for technical analysis.**

```python
{
    "symbol": "SPY",
    "periodType": "day",           # day, month, year, ytd
    "period": 10,                  # Number of periods
    "frequencyType": "minute",     # minute, daily, weekly, monthly
    "frequency": 5,                # Frequency within type
    "needExtendedHoursData": true,
    "needPreviousClose": true
}
```

### 3. Market Hours API (`GET /markets`)

**Trading hours for different markets.**

```python
GET /marketdata/v1/markets?markets=equity,option&date=2024-12-01
```

---

## Implementation Strategies

### 1. Data Collection Workflow

```python
class OptionsDataCollector:
    def __init__(self, symbols: List[str]):
        self.client = SchwabClient()
        self.symbols = symbols
        
    async def collect_comprehensive_data(self, symbol: str):
        """Collect all options data for a symbol"""
        
        # 1. Get expiration dates
        expirations = await self.get_expiration_chain(symbol)
        
        # 2. Get options chains for relevant expirations
        chains_data = {}
        for exp in expirations[:5]:  # Focus on next 5 expirations
            chain = await self.get_option_chain(
                symbol=symbol,
                fromDate=exp['expirationDate'],
                toDate=exp['expirationDate'],
                strikeCount=20
            )
            chains_data[exp['expirationDate']] = chain
            
        # 3. Get underlying quote
        underlying = await self.get_quote(symbol)
        
        # 4. Calculate metrics
        metrics = self.calculate_flow_metrics(chains_data, underlying)
        
        return {
            'symbol': symbol,
            'underlying': underlying,
            'expirations': expirations,
            'chains': chains_data,
            'metrics': metrics,
            'timestamp': datetime.now(timezone.utc)
        }
```

### 2. Real-Time Streaming Integration

```python
class OptionsStreamer:
    def __init__(self):
        self.websocket = None
        self.subscriptions = set()
        
    async def start_streaming(self):
        """Start WebSocket connection for real-time data"""
        
        # 1. Establish WebSocket connection
        self.websocket = await self.connect_websocket()
        
        # 2. Login to streaming service
        await self.login_streaming()
        
        # 3. Subscribe to options data
        await self.subscribe_to_options()
        
        # 4. Handle incoming messages
        async for message in self.websocket:
            await self.process_options_message(message)
            
    async def subscribe_to_options(self):
        """Subscribe to specific options contracts"""
        
        # Get ATM options for key expirations
        options_symbols = self.get_atm_options_symbols()
        
        subscription = {
            "service": "LEVELONE_OPTIONS",
            "command": "SUBS",
            "parameters": {
                "keys": ",".join(options_symbols),
                "fields": "0,2,3,4,8,10,19,28,37"  # Key fields
            }
        }
        
        await self.send_websocket_message(subscription)
```

### 3. Delta-Volume Flow Calculation

```python
def calculate_options_flow(self, options_data: dict) -> dict:
    """Calculate comprehensive options flow metrics"""
    
    call_delta_volume = 0.0
    put_delta_volume = 0.0
    call_volume = 0
    put_volume = 0
    
    # Process calls
    for expiry, strikes in options_data.get('callExpDateMap', {}).items():
        for strike, contracts in strikes.items():
            for contract in contracts:
                delta = contract.get('delta', 0.0)
                volume = contract.get('totalVolume', 0)
                
                if volume > 0:
                    call_delta_volume += abs(delta) * volume
                    call_volume += volume
    
    # Process puts  
    for expiry, strikes in options_data.get('putExpDateMap', {}).items():
        for strike, contracts in strikes.items():
            for contract in contracts:
                delta = contract.get('delta', 0.0)
                volume = contract.get('totalVolume', 0)
                
                if volume > 0:
                    put_delta_volume += abs(delta) * volume
                    put_volume += volume
    
    # Calculate derived metrics
    net_delta_volume = call_delta_volume - put_delta_volume
    delta_ratio = call_delta_volume / put_delta_volume if put_delta_volume > 0 else float('inf')
    
    # Determine sentiment
    sentiment = "Bullish" if net_delta_volume > 0 else "Bearish"
    sentiment_strength = abs(net_delta_volume) / (call_delta_volume + put_delta_volume)
    
    return {
        'call_delta_volume': call_delta_volume,
        'put_delta_volume': put_delta_volume,
        'net_delta_volume': net_delta_volume,
        'delta_ratio': delta_ratio,
        'call_volume': call_volume,
        'put_volume': put_volume,
        'total_volume': call_volume + put_volume,
        'sentiment': sentiment,
        'sentiment_strength': sentiment_strength,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
```

---

## Data Processing Workflows

### 1. Historical Analysis Pipeline

```python
class OptionsAnalysisPipeline:
    def __init__(self):
        self.database = OptionsDatabase()
        self.analyzer = OptionsAnalyzer()
        
    async def run_daily_analysis(self, symbols: List[str]):
        """Complete daily options analysis workflow"""
        
        for symbol in symbols:
            # 1. Collect current options data
            current_data = await self.collect_comprehensive_data(symbol)
            
            # 2. Store in database
            await self.database.store_options_data(current_data)
            
            # 3. Calculate technical indicators
            indicators = await self.analyzer.calculate_indicators(symbol)
            
            # 4. Identify unusual activity
            unusual_activity = await self.analyzer.detect_unusual_activity(symbol)
            
            # 5. Generate alerts if needed
            if unusual_activity['alert_level'] > 0.7:
                await self.send_alert(symbol, unusual_activity)
```

### 2. Real-Time Processing

```python
class RealTimeOptionsProcessor:
    def __init__(self):
        self.buffer = OptionsDataBuffer()
        self.calculator = FlowCalculator()
        
    async def process_streaming_data(self, message: dict):
        """Process real-time options streaming data"""
        
        # 1. Parse and validate message
        parsed_data = self.parse_options_message(message)
        
        # 2. Update data buffer
        self.buffer.update(parsed_data)
        
        # 3. Calculate flow metrics if buffer is ready
        if self.buffer.is_ready():
            flow_metrics = self.calculator.calculate_flow(self.buffer.get_data())
            
            # 4. Emit to clients
            await self.emit_flow_update(flow_metrics)
            
            # 5. Store in database
            await self.store_flow_metrics(flow_metrics)
```

---

## Error Handling & Rate Limits

### 1. Rate Limiting Strategy

```python
class RateLimitManager:
    def __init__(self):
        self.api_limits = {
            'options_chains': {'calls_per_minute': 120, 'calls_per_day': 10000},
            'streaming': {'concurrent_connections': 1, 'symbols_limit': 500},
            'quotes': {'calls_per_minute': 300, 'calls_per_day': 25000}
        }
        self.call_history = defaultdict(deque)
        
    async def check_rate_limit(self, endpoint: str) -> bool:
        """Check if API call is within rate limits"""
        
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old calls
        while (self.call_history[endpoint] and 
               self.call_history[endpoint][0] < minute_ago):
            self.call_history[endpoint].popleft()
            
        # Check current limit
        current_calls = len(self.call_history[endpoint])
        limit = self.api_limits[endpoint]['calls_per_minute']
        
        if current_calls >= limit:
            wait_time = 60 - (now - self.call_history[endpoint][0]).seconds
            await asyncio.sleep(wait_time)
            
        self.call_history[endpoint].append(now)
        return True
```

### 2. Error Recovery

```python
class ErrorHandler:
    def __init__(self):
        self.retry_config = {
            'max_retries': 3,
            'backoff_factor': 2,
            'timeout': 30
        }
        
    async def with_retry(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry"""
        
        for attempt in range(self.retry_config['max_retries']):
            try:
                return await func(*args, **kwargs)
                
            except (HTTPError, TimeoutError) as e:
                if attempt == self.retry_config['max_retries'] - 1:
                    raise e
                    
                wait_time = self.retry_config['backoff_factor'] ** attempt
                await asyncio.sleep(wait_time)
                
            except AuthenticationError:
                await self.refresh_tokens()
                # Retry with new tokens
                
            except RateLimitError as e:
                await asyncio.sleep(e.retry_after)
```

---

## Best Practices

### 1. Efficient Data Collection
- **Batch requests** when possible to minimize API calls
- **Focus on liquid options** (high volume, tight spreads)
- **Use appropriate strike ranges** based on volatility
- **Cache expiration data** to avoid redundant calls

### 2. Real-Time Streaming
- **Subscribe to key contracts only** (ATM, high volume)
- **Implement connection management** with automatic reconnection
- **Buffer data appropriately** for smooth calculations
- **Monitor connection health** and data quality

### 3. Data Storage
- **Separate tables** for chains, streaming, and calculated metrics
- **Implement data retention policies** for storage management
- **Use appropriate indexes** for time-series queries
- **Archive historical data** for long-term analysis

### 4. Performance Optimization
- **Async/await patterns** for concurrent API calls
- **Connection pooling** for database operations
- **Caching strategies** for frequently accessed data
- **Efficient data structures** for real-time calculations

---

This comprehensive guide provides the foundation for collecting and processing options data using the Schwab API. The implementation can be integrated with your existing market data streaming application to provide sophisticated options flow analysis capabilities.