# Pull Request Review: Cursor Hooks Logging & Redis Integration

**Date**: 2025-01-XX  
**Branch**: `claude/cursor-hooks-logging-redis-011CUzzFEs8ZFRGYXMPtzjid`  
**Reviewer**: AI Assistant

---

## Executive Summary

This PR implements Layer 1 Capture for the Cursor IDE platform, including Redis Streams message queue integration, 9 hook scripts, a TypeScript extension, and supporting infrastructure. The implementation is **mostly complete** but has **several critical issues** that need to be addressed before merging.

**Overall Status**: ⚠️ **Needs Changes** - Implementation is solid but has spec compliance issues

---

## ✅ What's Working Well

### 1. Architecture & Structure
- ✅ Clean separation between shared components and platform-specific code
- ✅ Proper use of base classes (`CursorHookBase`) for code reuse
- ✅ Well-organized directory structure following the architecture docs
- ✅ Good error handling with silent failure pattern

### 2. Redis Integration
- ✅ Proper Redis Streams implementation with XADD
- ✅ Connection pooling configured correctly
- ✅ Auto-trim with MAXLEN ~10000
- ✅ 1-second timeout implemented
- ✅ Dead Letter Queue (DLQ) support present
- ✅ Health checks and statistics methods

### 3. Hook Implementation
- ✅ All 9 required hooks implemented
- ✅ Proper command-line argument parsing
- ✅ Silent failure mode (always returns 0)
- ✅ Event building follows consistent pattern

### 4. Extension Implementation
- ✅ Session management with proper ID generation
- ✅ Workspace hash computation
- ✅ Database monitoring with dual strategy (file watcher + polling)
- ✅ Proper VSCode extension lifecycle management

---

## ❌ Critical Issues

### 1. **Message Format Mismatch** 🔴 **CRITICAL**

**Spec Requirement** (from `layer1_capture.md` lines 80-91):
```json
{
  "event_id": "...",
  "enqueued_at": "...",
  "retry_count": "0",
  "platform": "claude_code",
  "external_session_id": "...",
  "hook_type": "SessionStart",
  "timestamp": "...",
  "sequence_num": "1",
  "data": "{\"cwd\":\"/Users/user/project\",\"source\":\"startup\"}"
}
```

**Current Implementation** (`queue_writer.py` lines 167-186):
```python
stream_entry = {
    'event_id': event_id,
    'enqueued_at': enqueued_at,
    'retry_count': '0',
    'platform': platform,
    'external_session_id': session_id,
    'hook_type': event['hook_type'],
    'timestamp': event['timestamp'],
}
# Uses 'payload' and 'metadata' separately
if 'payload' in event:
    stream_entry['payload'] = json.dumps(event['payload'])
if 'metadata' in event:
    stream_entry['metadata'] = json.dumps(event['metadata'])
```

**Issues**:
- ❌ Spec requires `data` field (single JSON string), but implementation uses `payload` and `metadata` separately
- ❌ Missing `sequence_num` field entirely
- ❌ This will break Layer 2 consumers expecting the spec format

**Fix Required**:
- Combine `payload` and `metadata` into a single `data` field
- Add `sequence_num` tracking (per session)
- Update both Python and TypeScript queue writers

---

### 2. **Session ID Environment Variable Disconnect** 🔴 **CRITICAL**

**Spec Requirement** (`layer1_capture.md` line 272):
> Get session_id from environment variable CURSOR_SESSION_ID (set by extension)

**Current Implementation**:
- Extension (`sessionManager.ts` lines 104-127): Writes to workspace state and a file
- Hooks (`hook_base.py` line 65): Read from `os.environ.get('CURSOR_SESSION_ID')`

**Problem**:
- ❌ VSCode extensions **cannot set process environment variables** that persist to child processes
- ❌ Hooks will always get `None` for `CURSOR_SESSION_ID`
- ❌ Extension writes to file but hooks don't read from file

**Fix Required**:
- Option A: Hooks read from the file written by extension (`~/.cursor-session-env` or similar)
- Option B: Use Cursor's hooks.json environment variable template system (which uses `${sessionId}`)
- Option C: Use IPC mechanism between extension and hooks

**Note**: `hooks.json` already has environment variable templates (lines 146-149), but the extension needs to ensure these are actually set when hooks run.

---

### 3. **Missing Sequence Number Tracking** 🟡 **HIGH**

**Spec Requirement** (`layer1_capture.md` line 89):
```json
"sequence_num": "1"
```

**Current Implementation**:
- ❌ No sequence number tracking in hooks
- ❌ No sequence number in event building
- ❌ No sequence number in queue writer

**Fix Required**:
- Add sequence number counter per session
- Store in extension state or file
- Increment on each event
- Include in all events

---

### 4. **Cursor Hook Input Format Mismatch** 🟡 **MEDIUM**

**Spec Document** (`layer1_cursor_hook_output.md` line 5):
> Cursor hooks receive JSON input via stdin

**Current Implementation**:
- ✅ Uses command-line arguments (which matches `hooks.json` configuration)
- ✅ This is likely correct for Cursor's actual implementation

**Status**: This appears to be a **documentation issue** rather than implementation issue. The spec doc may be outdated or describe a different hook system. However, this should be clarified.

**Recommendation**: Verify with Cursor documentation or update spec to match actual Cursor hook behavior.

---

### 5. **Missing Prompt Text Capture** 🟡 **MEDIUM**

**Spec Requirement** (`layer1_cursor_hook_output.md` lines 15-31):
```json
{
  "prompt": "User's actual prompt text here...",
  "context": {...}
}
```

**Current Implementation** (`before_submit_prompt.py`):
- ❌ Only captures `prompt_length`, not actual prompt text
- ❌ No context information captured

**Note**: This may be intentional for privacy reasons, but should be documented. If privacy is the concern, the spec should be updated to reflect this.

---

### 6. **Database Monitor Query Issues** 🟡 **MEDIUM**

**Current Implementation** (`databaseMonitor.ts` lines 208-212):
```typescript
const generations = this.db.prepare(
  `SELECT * FROM "aiService.generations"
   WHERE data_version > ? AND data_version <= ?
   ORDER BY data_version ASC`
).all(fromVersion, toVersion) as any[];
```

**Issues**:
- ❌ Spec mentions querying related prompt and composer data (lines 340-341 in `layer1_capture.md`), but implementation only processes generations
- ❌ No JOIN queries to get related data
- ❌ Missing prompt and composer data in trace events

**Fix Required**:
- Add queries for `aiService.prompts` table
- Add queries for `composer.composerData` table
- Include related data in trace events as specified

---

## ⚠️ Minor Issues & Improvements

### 1. **Error Handling in Extension**
- Extension shows warning if Redis unavailable but continues (good)
- However, hooks will silently fail without any user notification
- Consider adding a status bar indicator when Redis is down

### 2. **Configuration Loading**
- `Config` class has complex path finding logic (lines 66-82)
- May fail if config directory not found
- Consider more robust fallback to defaults

### 3. **Type Safety**
- TypeScript extension uses `any[]` for database results
- Could benefit from proper typing

### 4. **Testing**
- No tests visible in the PR
- Consider adding unit tests for critical paths

### 5. **Documentation**
- Missing docstrings in some hook files
- Extension README could be more detailed

---

## 📋 Required Changes Before Merge

### Must Fix (Blocking):
1. ✅ Fix message format to use `data` field instead of `payload`/`metadata`
2. ✅ Add `sequence_num` tracking and include in all events
3. ✅ Fix session ID environment variable mechanism (hooks must be able to read session ID)
4. ✅ Update database monitor to include prompt and composer data

### Should Fix (High Priority):
5. ✅ Clarify or fix Cursor hook input format (stdin vs command-line args)
6. ✅ Document privacy decisions (why prompt text not captured)
7. ✅ Add error handling improvements

### Nice to Have:
8. ⚪ Add unit tests
9. ⚪ Improve type safety
10. ⚪ Add more comprehensive documentation

---

## 🔍 Code Quality Assessment

### Strengths:
- ✅ Clean, readable code
- ✅ Good separation of concerns
- ✅ Proper error handling patterns
- ✅ Consistent code style
- ✅ Good use of enums and type definitions

### Areas for Improvement:
- ⚠️ Some missing type annotations in Python
- ⚠️ Could use more comprehensive docstrings
- ⚠️ Some magic numbers could be constants

---

## 📊 Spec Compliance Score

| Component | Compliance | Notes |
|-----------|-----------|-------|
| Redis Streams Format | ❌ 40% | Wrong field names, missing sequence_num |
| Hook Implementation | ✅ 90% | Missing some data fields |
| Session Management | ❌ 60% | Environment variable issue |
| Database Monitoring | ⚠️ 70% | Missing related data queries |
| Extension Lifecycle | ✅ 95% | Well implemented |
| Error Handling | ✅ 85% | Good silent failure pattern |
| **Overall** | **⚠️ 73%** | **Needs fixes before merge** |

---

## 🎯 Recommendations

1. **Immediate Action**: Fix the message format mismatch - this is critical for Layer 2 compatibility
2. **Session ID Fix**: Implement file-based session ID reading in hooks or use Cursor's environment variable system properly
3. **Add Sequence Numbers**: Implement per-session sequence number tracking
4. **Update Specs**: If Cursor hooks use command-line args (not stdin), update the spec document
5. **Testing**: Add integration tests to verify message format matches spec

---

## ✅ Approval Status

**Status**: ❌ **NOT READY FOR MERGE**

**Reason**: Critical spec compliance issues that will break Layer 2 integration.

**Next Steps**:
1. Address all "Must Fix" items
2. Re-review after fixes
3. Consider adding integration tests
4. Update documentation to match implementation

---

## 📝 Additional Notes

- The implementation shows good understanding of the architecture
- Code quality is generally high
- The issues are fixable and don't require major refactoring
- Once fixed, this should integrate well with Layer 2

---

**Review Completed**: [Date]  
**Reviewed By**: AI Assistant  
**Next Review**: After critical fixes implemented

