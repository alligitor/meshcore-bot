# Race Condition Fix for RF Data Correlation

## Problem Description

The MeshCore Bot was experiencing a race condition where channel messages would sometimes show "unknown" SNR/RSSI values instead of actual measurements. This occurred because:

1. **Event Timing Dependency**: The bot expected `RX_LOG_DATA` events (containing SNR/RSSI) to arrive before or very close to `CHANNEL_MSG_RECV` events
2. **Short Time Window**: The original 5-second correlation window was too narrow for network timing variations
3. **No Fallback Strategy**: When immediate correlation failed, there was no robust fallback mechanism

## Root Cause Analysis

From the logs, we can see the issue:
```
2025-09-04 17:24:42 - MeshCoreBot - WARNING - ❌ NO RF DATA found for channel message
```

This happened because:
- The `RX_LOG_DATA` event arrived outside the 5-second correlation window
- The events were processed in an unexpected order
- The timing gap between RF data and message events was too large

## Solutions Implemented

### 1. Extended Time Window
- **Before**: 5-second correlation window
- **After**: 15-second correlation window (configurable)
- **Benefit**: Handles network timing variations and device processing delays

### 2. Multi-Strategy Correlation System
The bot now uses 4 correlation strategies in sequence:

#### Strategy 1: Immediate Correlation
- Try to find RF data immediately using exact pubkey match
- Fastest and most accurate when events arrive in order

#### Strategy 2: Message Queuing (Enhanced Mode)
- Store messages temporarily and wait 100ms for RF data
- Only enabled when `enable_enhanced_correlation = true`
- Handles cases where RF data arrives slightly after message

#### Strategy 3: Extended Timeout
- Search with 2x the normal timeout (30 seconds)
- Catches RF data that arrived much earlier than expected

#### Strategy 4: Most Recent Fallback
- Use the most recent RF data available
- Ensures we always have some signal strength information

### 3. Improved Pubkey Matching
- **Exact Match**: Full pubkey comparison (most reliable)
- **Partial Match**: First 16 characters (handles truncated pubkeys)
- **Fallback**: Most recent data (handles timing issues)

### 4. Enhanced Data Storage
- **Timestamp Index**: Fast lookup by time
- **Pubkey Index**: Fast lookup by sender
- **Automatic Cleanup**: Removes old data to prevent memory leaks

### 5. Configuration Options
Added to `config.ini`:
```ini
[Bot]
# RF Data Correlation Settings
rf_data_timeout = 15.0                    # Time window for correlation
message_correlation_timeout = 10.0        # Time to wait for correlation
enable_enhanced_correlation = true        # Enable advanced strategies
```

## Performance Impact

### Positive Impacts
- **Higher Success Rate**: More messages will have accurate SNR/RSSI values
- **Better User Experience**: Users see actual signal strength instead of "unknown"
- **Robust Operation**: Handles network timing variations gracefully

### Minimal Overhead
- **Memory**: Slightly more memory for correlation indexes (cleaned up automatically)
- **CPU**: Negligible impact from additional correlation attempts
- **Latency**: 100ms additional wait only when needed (Strategy 2)

## Testing Results

All correlation strategies tested successfully:
- ✅ Immediate correlation
- ✅ Message correlation system  
- ✅ Extended timeout correlation
- ✅ Partial pubkey matching
- ✅ Cleanup functionality

## Configuration Recommendations

### For Stable Networks
```ini
rf_data_timeout = 10.0
enable_enhanced_correlation = false
```

### For Unstable Networks (Default)
```ini
rf_data_timeout = 15.0
enable_enhanced_correlation = true
```

### For Very Unstable Networks
```ini
rf_data_timeout = 30.0
enable_enhanced_correlation = true
```

## Monitoring

The bot now logs correlation success/failure:
- `🔍 FOUND RF DATA`: Successful correlation
- `❌ NO RF DATA found for channel message after all correlation attempts`: All strategies failed

Monitor these logs to tune the configuration for your network conditions.

## Backward Compatibility

- All changes are backward compatible
- Default configuration provides improved behavior
- Can be disabled by setting `enable_enhanced_correlation = false`
- Original 5-second behavior available by setting `rf_data_timeout = 5.0`

## Future Improvements

1. **Adaptive Timeouts**: Automatically adjust timeouts based on network conditions
2. **Machine Learning**: Learn optimal correlation strategies from historical data
3. **Network Quality Metrics**: Track correlation success rates and adjust accordingly
4. **Event Ordering**: Implement event sequence numbers for more reliable correlation
