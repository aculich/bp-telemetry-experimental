# Missing Markdown Generation Features

## Comparison: Current Python Implementation vs Reference JavaScript Implementation

### Current Output (Python)
The Python implementation currently only shows:
- Composer metadata (IDs, creation dates, modes, code changes)
- Basic composer statistics
- No actual conversation messages
- No model information
- No speaker labels
- No message timestamps

### Expected Output (Reference JavaScript)
The reference implementation shows:
- **Full conversation messages** with user/assistant content
- **Model information** (e.g., "model claude-3-5-sonnet-20241022")
- **Speaker labels** ("User", "Agent (model X, mode Y)")
- **Message timestamps** for each message
- **Tool usage** formatted with collapsible details
- **Thinking/reasoning** content (if available)

## Missing Functionality

### 1. Conversation Message Loading
**Status**: ❌ Missing

**Current**: Only loads `composer.composerData` which contains metadata (`allComposers` list)

**Needed**: Load full composer objects with `conversation` array containing actual messages

**Reference Implementation** (`markdownGenerator.js:140-169`):
```javascript
function normalizeCursorComposer(composerData) {
  // composerData contains:
  // - composerId
  // - name
  // - conversation: [messages...]  // <-- MISSING
  // - modelConfig: { modelName }
  // - capabilities: [...]
  // - createdAt, lastUpdatedAt
  
  return {
    id: composerData.composerId,
    name: composerData.name ?? "Untitled",
    conversation: (composerData.conversation || []).map((msg) =>
      normalizeCursorMessage(msg, capabilitiesMap, composerData._v, modelName)
    ),
    // ...
  };
}
```

### 2. Message Normalization
**Status**: ❌ Missing

**Needed**: Normalize raw Cursor messages to unified format with:
- `speaker`: "user" or "assistant"
- `text`: Message content
- `timestamp`: Unix milliseconds
- `modelName`: From `modelInfo.modelName` or `modelConfig.modelName`
- `agentMode`: String ("Ask", "Agent", "Plan")
- `type`: Capability type (0 = regular, 15 = tool usage)

**Reference Implementation** (`markdownGenerator.js:203-250`):
```javascript
function normalizeCursorMessage(message, capabilitiesMap, version, modelName) {
  const normalizedMessage = {
    messageId: message.bubbleId,
    speaker: message.type === 1 ? "user" : "assistant",
    text: message.thinking?.text
      ? `<think>...${message.thinking.text}...</think>`
      : message.text,
    timestamp: message.timingInfo?.clientStartTime,
    type: message.capabilityType,
    modelName: message?.modelInfo?.modelName ?? modelName ?? "",
    agentMode: getAgentModeString(message?.unifiedMode),
  };
  
  // Handle tool usage (capabilityType 15)
  if (message.capabilityType === 15) {
    adaptToolUse(normalizedMessage, bubbleData);
  }
  
  return normalizedMessage;
}
```

### 3. Model Information Extraction
**Status**: ❌ Missing

**Current**: No model information displayed

**Needed**: Extract and display model name from:
- `composerData.modelConfig.modelName` (composer-level default)
- `message.modelInfo.modelName` (message-level override)

**Reference Implementation** (`markdownGenerator.js:153-158, 225, 631`):
```javascript
// Extract from composer
const modelName = composerData.modelConfig?.modelName;

// Extract from message
modelName: message?.modelInfo?.modelName ?? modelName ?? ""

// Display in markdown
const modelInfo = message.modelName ? `model ${message.modelName}` : "";
speakerLabel += ` (${modelInfo}, ${modeInfo})`;
```

### 4. Conversation Formatting
**Status**: ❌ Missing

**Current**: Only shows composer headers with metadata

**Needed**: Format actual conversation messages with:
- Speaker headers when speaker changes
- Model and mode info in assistant headers
- Message timestamps
- Message content
- Tool usage sections

**Reference Implementation** (`markdownGenerator.js:580-649`):
```javascript
function generateConversationMarkdown(conversation, useUtc = false) {
  // Header with name and creation date
  markdown += `# ${conversation.name} (${createdAtFormatted})\n\n`;
  
  for (const message of conversation.conversation) {
    const isUser = message.speaker === "user";
    let speakerLabel = isUser ? "User" : "Agent";
    
    // Add speaker header when speaker changes
    if (message.speaker !== lastSpeaker) {
      if (isUser) {
        // User: show timestamp from next assistant message
        speakerLabel = `${speakerLabel} (${nextAssistantTimestamp})`;
      } else {
        // Assistant: show model and mode
        const modelInfo = message.modelName ? `model ${message.modelName}` : "";
        const modeInfo = message.agentMode ? `mode ${message.agentMode}` : "";
        speakerLabel += ` (${modelInfo}, ${modeInfo})`;
      }
      markdown += `_**${speakerLabel}**_\n\n`;
    }
    
    markdown += `${message.text}\n\n---\n\n`;
  }
}
```

### 5. Tool Usage Handling
**Status**: ❌ Missing

**Needed**: Format tool usage messages (capabilityType 15) with:
- Tool name and type
- Formatted arguments
- Formatted results
- Error handling
- Collapsible `<details>` sections

**Reference Implementation** (`markdownGenerator.js:250-556`):
- `adaptToolUse()` - Routes to tool-specific handlers
- Tool handlers: `ReadFileToolHandler`, `CodebaseSearchToolHandler`, `TodoWriteToolHandler`, `SearchReplaceToolHandler`, etc.
- Wraps output in `<tool-use>` tags

### 6. Capabilities Map Building
**Status**: ❌ Missing

**Needed**: Build capabilities map from `composerData.capabilities` to support tool usage:
- Parse `bubbleDataMap` JSON strings
- Map capability types to data
- Extract tool usage data for messages

**Reference Implementation** (`markdownGenerator.js:141-150`):
```javascript
const capabilitiesMap = new Map();
for (const capability of composerData.capabilities || []) {
  const capabilityData = { ...capability.data };
  if (capabilityData.bubbleDataMap) {
    capabilityData.bubbleDataMap = JSON.parse(capabilityData.bubbleDataMap);
  }
  capabilitiesMap.set(capability.type, capabilityData);
}
```

### 7. Agent Mode String Conversion
**Status**: ❌ Missing

**Needed**: Convert unified mode numbers to strings:
- 1 → "Ask"
- 2 → "Agent"
- 5 → "Plan"

**Reference Implementation** (`markdownGenerator.js:124-135`):
```javascript
function getAgentModeString(unifiedMode) {
  switch (unifiedMode) {
    case 1: return "Ask";
    case 2: return "Agent";
    case 5: return "Plan";
    default: return unifiedMode ? "Custom" : "";
  }
}
```

### 8. Timestamp Formatting
**Status**: ⚠️ Partial

**Current**: Basic timestamp formatting exists

**Needed**: Enhanced formatting matching reference:
- Display format: "YYYY-MM-DD HH:MM:SS+offset"
- Filename format: "YYYY-MM-DD_HH-MM-SS"
- Handle Unix milliseconds
- Support UTC vs local timezone

**Reference Implementation** (`markdownGenerator.js:83-109`):
```javascript
function formatTimestampForDisplay(timestamp, defaultText, useUtc = false) {
  const components = formatDateComponents(date, useUtc);
  return `${year}-${month}-${day} ${hour}:${minute}${offset}`;
}
```

## Data Structure Differences

### Expected Composer Data Structure
```javascript
{
  host: "cursor",
  composerId: "uuid",
  name: "Untitled",
  createdAt: 1762033584314,
  lastUpdatedAt: 1762033584314,
  _v: 3,
  modelConfig: {
    modelName: "claude-3-5-sonnet-20241022"
  },
  capabilities: [
    {
      type: 15,
      data: {
        bubbleDataMap: JSON.stringify({...})
      }
    }
  ],
  conversation: [  // <-- THIS IS MISSING IN CURRENT OUTPUT
    {
      bubbleId: "msg-1",
      type: 1,  // 1 = user, 2 = assistant
      text: "How do I implement authentication?",
      timingInfo: {
        clientStartTime: 1762033584314,
        // ...
      },
      capabilityType: 0,  // 0 = regular, 15 = tool usage
      unifiedMode: 2,  // 1 = Ask, 2 = Agent, 5 = Plan
      modelInfo: {
        modelName: "claude-3-5-sonnet-20241022"
      },
      thinking: {
        text: "..."  // Optional reasoning
      },
      toolFormerData: {  // If capabilityType === 15
        name: "read_file",
        rawArgs: JSON.stringify({...}),
        result: JSON.stringify({...}),
        status: "success"
      }
    }
  ]
}
```

### Current Composer Data Structure (from Python)
```python
{
  "allComposers": [
    {
      "composerId": "uuid",
      "createdAt": 1762033584314,
      "unifiedMode": "agent",
      "forceMode": "edit",
      "totalLinesAdded": 0,
      "totalLinesRemoved": 0,
      "isArchived": False
    }
  ],
  "selectedComposerIds": [...],
  "lastFocusedComposerIds": [...]
}
```

## Implementation Priority

1. **HIGH**: Load full composer data with conversation messages
2. **HIGH**: Normalize messages (speaker, text, timestamps, model info)
3. **HIGH**: Format conversations with speaker labels and model info
4. **MEDIUM**: Tool usage handling and adaptation
5. **MEDIUM**: Capabilities map building
6. **LOW**: Enhanced timestamp formatting
7. **LOW**: Agent mode string conversion

## Next Steps

1. Investigate how to load full composer data (not just metadata)
   - May need to query different keys
   - May need to use `editorStorageService.getAllWorkspaceComposers()` equivalent
2. Implement message normalization functions
3. Implement conversation formatting with speaker labels
4. Add model information extraction and display
5. Add tool usage handling

