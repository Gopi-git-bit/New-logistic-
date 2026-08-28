# PRD — Agents (§15 Harness, Hermes, Paperclip, Honcho)

> Source of truth for all AI agent specifications.

## 1. Agent Architecture

### 7 + 1 Agent System

| # | Agent | Role | Goal |
|---|-------|------|------|
| 1 | Customer Service | Unified customer interface | Single point of contact for all customer needs |
| 2 | Order Management | Lifecycle orchestration | Order-to-provider matching, workflow automation |
| 3 | Transportation | Route optimization | Real-time tracking, ETA calculation, incident response |
| 4 | Resource Management | Fleet + company relationships | Vehicle/driver availability, inter-company coordination |
| 5 | Payment & Settlement | Financial transactions | Payment processing, commission calculation, settlements |
| 6 | Platform Administration | Governance + compliance | System oversight, policy enforcement, AI regulation |
| 7 | Communication | Multi-channel notifications | Push, SMS, email, in-app messaging |
| 8 | Document Processing | OCR + document management | POD capture, document verification, cloud storage |

## 2. Agent Service Layer

### Base Class
```python
class BaseAgentService(ABC):
    agent_name: str  # Auto-derived from class name
    
    @abstractmethod
    def process_task(self, task_data: dict) -> dict:
        """Process a task assigned to this agent"""
        pass
    
    def log_activity(self, action, details, user=None):
        """Log agent activity to ai_agent_activities"""
        pass
    
    def communicate_with_agent(self, target_agent, message_data):
        """Send message to another agent via Redis queue"""
        pass
```

### Communication
- **Transport**: Redis message queue (`agent_messages`)
- **Format**: JSON with `from_agent`, `to_agent`, `message_data`, `timestamp`, `message_id`
- **Processing**: Background task (`process_agent_messages`) polls queue
- **Logging**: All communications logged to `agent_communication_log`

## 3. LoopGuardian (Safety Gates)

Every agent task passes through LoopGuardian before execution:

| Gate | Description | Action on Failure |
|------|-------------|-------------------|
| **Cap** | Max tool calls per tick (default: 20) | Pause agent, log intervention |
| **Malformed** | Invalid/malformed query detection | Reject task, log intervention |
| **Hallucination** | Output anomaly detection | Suspend agent, notify admin |
| **Infinite Loop** | Repetitive action detection | Break loop, log intervention |
| **Budget** | Daily USD spend limit | Pause agent until next day |

## 4. Agent Capabilities Matrix

| Agent | place_order | assign_driver | update_delivery | match_drivers | generate_quote | validate_payment | process_document | send_notification |
|-------|:-----------:|:-------------:|:---------------:|:-------------:|:--------------:|:----------------:|:----------------:|:-----------------:|
| customer_service | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| order_management | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| transportation | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| resource_management | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| payment_settlement | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| platform_administration | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| communication | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| document_processing | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |

## 5. Task Queue

### Durable Queue (`agent_tasks`)
- **Claim**: `SKIP LOCKED` for concurrent safety
- **Priority**: 1 (critical) → 5 (background)
- **Retry**: 3 attempts before dead-letter
- **Deduplication**: `dedupe_key` unique constraint
- **Timeout**: Configurable per agent

### Task States
```
pending → claimed → completed
                  → failed → retry → failed → retry → failed → dead_letter
```

## 6. Hermes (DeepSeek Integration)

**Status**: Not started (M7)

### Planned Features
- DeepSeek V4 Pro for complex planning
- DeepSeek V4 Flash for fast execution
- OpenRouter routing for model selection
- Fallback chain: DeepSeek → OpenAI → Anthropic

### Model Routing
| Task Type | Model | Rationale |
|-----------|-------|-----------|
| Complex planning | `deepseek-v4-pro` | Accuracy优先 |
| Fast execution | `deepseek-v4-flash` | Speed优先 |
| Vision tasks | `MODEL_VISION` | PRD R1 TBD |

## 7. Paperclip (Decision Framework)

**Status**: Not started (M7)

### Planned Features
- Deterministic decision trees for business logic
- HITL (Human-in-the-Loop) for high-impact decisions
- Decision locks to prevent agent self-approval
- Audit trail for all decisions

### Decision Categories
| Category | Auto/HITL | Examples |
|----------|-----------|----------|
| Pricing | Auto | Quote generation, commission calculation |
| Assignment | Auto | Driver matching, vehicle selection |
| Payment | HITL | Refunds > ₹10,000, disputes |
| Suspension | HITL | User/account suspension |
| Compliance | HITL | Policy violations, fraud alerts |

## 8. Honcho (Memory System)

**Status**: Not started (M7)

### Planned Features
- Long-term memory for agent interactions
- Customer preference learning
- Context retention across sessions
- Semantic search over conversation history

### Deployment Options
| Option | Pros | Cons |
|--------|------|------|
| Self-hosted | Full control, no vendor lock | Infrastructure overhead |
| Managed | Easy setup, maintenance included | Vendor dependency, cost |

**Decision**: R9 pending — Self-hosted recommended for control.

## 9. Agent Activity Monitoring

### Activity Log (`ai_agent_activities`)
- Agent name + type
- Activity type + details
- Input/output data
- Confidence score
- Execution time (ms)
- Status (pending/completed/failed/interrupted)

### Intervention Log (`ai_agent_interventions`)
- Intervention type (hallucination, error_correction, performance_issue, anomaly_detection)
- Detection method
- Original vs corrected output
- Confidence scores before/after
- Resolution status

### Admin Dashboard
- Real-time agent performance metrics
- Hallucination detection alerts
- Model retraining triggers
- Algorithm adjustment interface

## 10. Integration Points

| System | Agent | Integration |
|--------|-------|-------------|
| Odoo 18 CE | order_management, resource_management | JSON-RPC, invoice sync |
| Razorpay | payment_settlement | Webhook + API |
| Mapbox | transportation | Directions + Traffic API |
| Langfuse | All agents | Observability + tracing |
| DeepSeek | All agents | LLM inference via OpenRouter |
| Tesseract | document_processing | OCR extraction |
| Twilio/Resend | communication | SMS + Email delivery |
