# Timing Diagram: Before and After Fix

## BEFORE FIX (Problematic Behavior)

```
Timeline:
0s     User clicks "Start Auto-Ingest" in web UI
       └─> POST /api/auto-ingest-snakemake/start
           └─> AutoIngestService.start()
               └─> _maybe_start_processing()
                   └─> Thread.start(_run_snakemake_workflow)
                       └─> ACQUIRES _snakemake_lock ◄── LOCK HELD HERE
                           └─> subprocess.Popen(snakemake...)
                               └─> for line in stdout:  ◄── STILL HOLDING LOCK
                                   └─> logger.info(line)
                                   
10s    User tries to check status
       └─> GET /api/auto-ingest-snakemake/status
           └─> get_status()
               └─> BLOCKS waiting for _snakemake_lock ✗
                   └─> REQUEST HANGS FOREVER...

30s    User tries to check progress
       └─> GET /api/auto-ingest-snakemake/progress
           └─> get_progress()
               └─> BLOCKS waiting for _snakemake_lock ✗
                   └─> REQUEST HANGS FOREVER...

60s    Snakemake still running...
       └─> stdout.read() still holding lock ✗
       
300s   Snakemake completes
       └─> process.wait() returns
           └─> RELEASES _snakemake_lock ◄── LOCK FINALLY RELEASED
               └─> All blocked requests suddenly complete

RESULT: Web UI frozen for 5 minutes! ✗
```

## AFTER FIX (Correct Behavior)

```
Timeline:
0s     User clicks "Start Auto-Ingest" in web UI
       └─> POST /api/auto-ingest-snakemake/start
           └─> AutoIngestService.start()
               └─> _maybe_start_processing()
                   └─> Thread.start(_run_snakemake_workflow)
                       └─> ACQUIRES _snakemake_lock ◄── LOCK ACQUIRED
                           └─> subprocess.Popen(snakemake...)
                           └─> process = _snakemake_process
                       └─> RELEASES _snakemake_lock ◄── LOCK RELEASED (0.001s)
                       └─> for line in stdout:  ◄── NO LOCK HELD
                           └─> logger.info(line)

1s     User tries to check status
       └─> GET /api/auto-ingest-snakemake/status
           └─> get_status()
               └─> ACQUIRES _snakemake_lock (instantly) ✓
                   └─> is_processing = _snakemake_process.poll()
               └─> RELEASES _snakemake_lock
               └─> Returns: {"is_processing": true} ✓
       └─> Response time: 0.02s ✓

5s     User tries to check progress
       └─> GET /api/auto-ingest-snakemake/progress
           └─> get_progress()
               └─> ACQUIRES _snakemake_lock (instantly) ✓
                   └─> is_processing = _snakemake_process.poll()
               └─> RELEASES _snakemake_lock
               └─> HTTP GET to logger API
               └─> Returns: {"total_jobs": 10, "completed": 3} ✓
       └─> Response time: 0.15s ✓

60s    Snakemake still running...
       └─> stdout.read() NOT holding lock ✓
       └─> All API calls still responsive ✓
       
300s   Snakemake completes
       └─> process.wait() returns
       └─> ACQUIRES _snakemake_lock
           └─> _snakemake_process = None
       └─> RELEASES _snakemake_lock

RESULT: Web UI responsive throughout! ✓
```

## Key Differences

### Lock Duration
- **Before**: Lock held for 300 seconds (entire Snakemake run)
- **After**: Lock held for ~0.001 seconds (twice: start + end)

### API Response Time
- **Before**: Infinite (hangs until Snakemake completes)
- **After**: < 0.5 seconds (normal response time)

### User Experience
- **Before**: UI freezes, appears broken, users think server crashed
- **After**: UI shows real-time progress, users can monitor workflow

## Technical Details

### Critical Section Protection
Only these operations need the lock:
1. **Setting** `_snakemake_process` (startup)
2. **Reading** `_snakemake_process` for status checks
3. **Clearing** `_snakemake_process` (cleanup)

These are fast operations (< 1ms), so holding the lock is safe.

### Non-Critical Operations
These do NOT need the lock:
1. **Streaming** stdout (blocking I/O, could take hours)
2. **Waiting** for process completion (blocking, could take hours)
3. **Logging** output lines (I/O operation)

These are moved outside the lock to allow concurrent access.

## Visualization of Lock Scope

```
BEFORE (Lock held for hours):
┌─────────────────────────────────────────────────────────┐
│ _snakemake_lock held                                    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Create process (1ms)                            │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Stream stdout (hours!)                          │   │
│  │ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ... thousands of lines ... │   │
│  │ └──┘ └──┘ └──┘ └──┘                             │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Wait for completion (hours!)                    │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Clear process (1ms)                             │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘

AFTER (Lock held for milliseconds):
┌───────────────────┐                   ┌───────────────────┐
│ _snakemake_lock   │                   │ _snakemake_lock   │
│                   │                   │                   │
│ ┌───────────────┐ │                   │ ┌───────────────┐ │
│ │Create process │ │                   │ │Clear process  │ │
│ │    (1ms)      │ │                   │ │    (1ms)      │ │
│ └───────────────┘ │                   │ └───────────────┘ │
└───────────────────┘                   └───────────────────┘
      ▲                                         ▲
      └─────────────────┐       ┌───────────────┘
                        │       │
            ┌───────────▼───────▼──────────┐
            │ Stream stdout (hours)        │
            │ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ...     │
            │ └──┘ └──┘ └──┘ └──┘          │
            └──────────────────────────────┘
            ┌──────────────────────────────┐
            │ Wait for completion (hours)  │
            └──────────────────────────────┐
                                           │
            NO LOCK HELD ─────────────────►│
            Other threads can access       │
            _snakemake_process via         │
            their own brief lock           │
            acquisitions                   │
```
