---
name: code-analysis-branch-testing
description: >
  Code analysis and branch testing skill based on pre-built code index.
  Uses Coordinator to dispatch multiple Workers for concurrent analysis,
  leveraging code symbol index, call graph, and annotation index to locate 
  transaction entry points, analyze UCC/BS/DAO call chains layer by layer,
  identify code branch conditions, generate test data (SQL + request messages) 
  covering different branches, execute tests and verify results.
  Suitable for Java 8 + Spring + MyBatis architecture with SOA service registry.
version: 2.0.0
tools_dir: tools
required_workers:
  - entry_locator
  - call_tracer
  - branch_analyzer
  - sql_generator
  - request_builder
  - test_executor
  - report_generator
allowed_tools:
  # === Code Intelligence Query Tools (Query Pre-built Index) ===
  - search_symbol
  - get_call_chain
  - find_by_annotation
  - read_method_source
  
  # === Database Operation Tools ===
  - connect_database
  - query_table_structure
  - execute_sql
  
  # === HTTP Communication Tool ===
  - send_request
tags: [code-analysis, branch-testing, java, spring, mybatis, coverage, coordinator-workers]
---

# Code Analysis and Branch Testing Expert

## Overview

This Skill provides end-to-end branch testing capabilities for Java Spring projects based on **pre-built code index + multi-Worker concurrent analysis** architecture:

- **Smart Entry Location**: Quickly locate transaction entry points via annotation index (`@TransCode`) or symbol search
- **Call Chain Tracing**: Unfold complete UCC → BS → DAO linkages using pre-built call graphs
- **Branch Analysis**: Identify conditional branches (IF/ELSE/SWITCH), establish mapping between request parameters and branches
- **Data Generation**: Generate DELETE/INSERT SQL covering various branches based on table structures
- **Test Execution**: Assemble request messages, execute tests and verify responses

## Architecture

```
User Request: "Analyze transaction code LN_LOAN_APPLY"
           ↓
┌─────────────────────┐
│   Coordinator       │  Create AnalysisSession, orchestrate Phases
│   (Node.js Server)  │
└──────────┬──────────┘
           │ Parallel spawn Workers
           ▼
Phase 1: [EntryLocator Worker × 2]
  ├─ Find via annotation index: @TransCode("LN_LOAN_APPLY")
  └─ Find via Spring route configuration
  
Phase 2: [CallTracer Worker] (Depends on P1)
  └─ Query get_call_chain(entry_fqn, depth=5) to unfold linkages
  
Phase 3: [BranchAnalyzer Worker] (Depends on P2)
  └─ Read source code of each layer, identify branch conditions
  
Phase 4: [SQLGenerator Worker] (Depends on P3)
  └─ Query table structures, generate SQL covering all branches
  
Phase 5: [RequestBuilder Worker] (Depends on P3)
  └─ Assemble JSON request messages
  
Phase 6: [TestExecutor Worker] (Depends on P4, P5)
  └─ Execute SQL → Send request → Verify response
  
Phase 7: [ReportGenerator Worker] (Depends on All)
  └─ Aggregate and generate test report
```

## Prerequisites

- **Code Index Built**: Target codebase has been parsed by tree-sitter and indexed (symbol table, call graph, annotation index)
- **Database Accessible**: Test environment database connection available
- **Service Reachable**: Target service endpoint accessible
- **Local Path Access**: Codebase located at server local path (e.g., `/data/codebases/loan-system`)

## Worker Division and Tool Usage

### EntryLocator Worker
**Goal**: Locate entry method corresponding to transaction code

**Tools Used**:
- `find_by_annotation("@TransCode", "LN_LOAN_APPLY")` → Primary: annotation search
- `search_symbol("*LN_LOAN_APPLY*", type="METHOD")` → Fallback: fuzzy search
- `search_symbol("*Controller", type="CLASS")` → Browse controller classes

**Output Format**:
```json
{
  "entry_point": {
    "fqn": "com.bank.loan.controller.LoanController.apply",
    "file": "src/main/java/com/bank/loan/controller/LoanController.java",
    "line": 45,
    "method_signature": "public Response apply(LoanRequest request)",
    "source": "annotation"
  },
  "confidence": 0.95
}
```

### CallTracer Worker
**Goal**: Unfold complete call chain (UCC → BS → DAO)

**Tools Used**:
- `get_call_chain(entry_fqn, direction="downstream", depth=5)` → Trace downstream calls
- `read_method_source(fqn, max_tokens=2000)` → Read key method source code

**Output Format**:
```json
{
  "call_chain": [
    {
      "depth": 0,
      "layer": "UCC",
      "fqn": "com.bank.loan.LoanController.apply",
      "summary": "Receive request, validate parameters, call LoanService"
    },
    {
      "depth": 1,
      "layer": "BS",
      "fqn": "com.bank.loan.LoanService.submitApplication",
      "calls_db": ["LoanMapper.insertApplication"],
      "calls_external": ["CreditService.queryReport"],
      "summary": "Business orchestration: save application record, call credit query"
    },
    {
      "depth": 2,
      "layer": "DAO",
      "fqn": "com.bank.loan.mapper.LoanMapper.insertApplication",
      "sql_id": "insertApplication",
      "summary": "MyBatis insert operation"
    }
  ],
  "external_calls": [
    {
      "layer": "BS",
      "fqn": "com.bank.credit.CreditService.queryReport",
      "protocol": "SOAP",
      "service_id": "credit-service"
    }
  ]
}
```

### BranchAnalyzer Worker
**Goal**: Analyze branch logic in each layer

**Tools Used**:
- `read_method_source(fqn, include_body=true)` → Read complete method body

**Analysis Content**:
- IF/ELSE conditional expressions
- SWITCH/CASE branches
- Boundary conditions (null checks, range judgments)
- Exception branches (try-catch)

**Output Format**:
```json
{
  "branches": [
    {
      "fqn": "com.bank.loan.LoanService.submitApplication",
      "conditions": [
        {
          "type": "IF",
          "expression": "request.getAmount() > 1000000",
          "branches": {
            "true": "Requires risk control approval",
            "false": "Auto approval"
          },
          "input_mapping": {
            "amount": {
              "trigger_true": "> 1000000",
              "trigger_false": "<= 1000000"
            }
          }
        },
        {
          "type": "SWITCH",
          "expression": "request.getLoanType()",
          "cases": [
            {"value": "PERSONAL", "behavior": "Personal loan processing"},
            {"value": "ENTERPRISE", "behavior": "Enterprise loan processing"},
            {"value": "default", "behavior": "Throw parameter error"}
          ]
        }
      ]
    }
  ]
}
```

### SQLGenerator Worker
**Goal**: Generate test SQL covering all branches

**Tools Used**:
- `connect_database(connection_string)` → Establish connection
- `query_table_structure("LOAN_APPLICATION")` → Query table structure
- `write_file` (base tool) → Output SQL files

**Generation Strategy**:
- **DELETE**: Clean test data (by business primary key)
- **INSERT**: Construct data for different branch scenarios
  - Large amount (>1M) → Trigger risk control branch
  - Small amount (<1M) → Auto approval branch
  - Different loan types (PERSONAL/ENTERPRISE)

**Output Format**:
```json
{
  "sql_files": [
    {
      "file": "test_data/case_1_large_amount.sql",
      "description": "Large amount scenario - trigger risk control branch",
      "target_branch": "amount > 1000000",
      "statements": [
        {"type": "DELETE", "table": "LOAN_APPLICATION", "condition": "loan_id = 'TEST001'"},
        {"type": "INSERT", "table": "LOAN_APPLICATION", "data": {"loan_id": "TEST001", "amount": 1500000, "type": "PERSONAL"}}
      ]
    }
  ]
}
```

### RequestBuilder Worker
**Goal**: Assemble HTTP request messages

**Input**: Branch analysis results (parameter structure, trigger conditions)

**Output**:
```json
{
  "request": {
    "method": "POST",
    "url": "http://gateway.bank.com/api/loan/apply",
    "headers": {
      "Content-Type": "application/json",
      "service_id": "LN_LOAN_APPLY"
    },
    "body": {
      "loan_id": "TEST001",
      "amount": 1500000,
      "loan_type": "PERSONAL",
      "applicant_name": "Test User",
      "id_no": "110101199001011234"
    }
  }
}
```

### TestExecutor Worker
**Goal**: Execute complete test flow

**Tools Used**:
- `execute_sql(sql, type="DELETE")` → Execute preparation SQL
- `execute_sql(sql, type="INSERT")` → Insert test data
- `send_request(request_config)` → Send request

**Validation Logic** (Agent reasoning):
- Is response status code 200
- Is code in response body "SUCCESS"
- Does database state match expectation (e.g., record status becomes "PENDING_REVIEW" indicates risk control triggered)

**Output**:
```json
{
  "test_results": [
    {
      "case_name": "Large Amount Risk Control Branch",
      "status": "PASSED",
      "steps": [
        {"step": "execute_delete", "status": "success"},
        {"step": "execute_insert", "status": "success"},
        {"step": "send_request", "status": "success", "response_time_ms": 245},
        {"step": "validate_response", "status": "success", "actual": {"code": "SUCCESS", "data": {"review_required": true}}}
      ],
      "branch_triggered": "amount > 1000000"
    }
  ]
}
```

### ReportGenerator Worker
**Goal**: Aggregate and generate test report

**Input**: Structured results from all phase Workers

**Output**: Markdown/HTML format test report

## Analysis Output Pattern

Structured data format passed between Workers:

```json
{
  "analysis_session": {
    "session_id": "uuid",
    "trans_code": "LN_LOAN_APPLY",
    "codebase_path": "/data/codebases/loan-system",
    "phases": {
      "entry_location": { "status": "completed", "worker_id": "worker_1", "result": {...} },
      "call_tracing": { "status": "completed", "worker_id": "worker_2", "result": {...} },
      "branch_analysis": { "status": "completed", "worker_id": "worker_3", "result": {...} },
      "sql_generation": { "status": "completed", "worker_id": "worker_4", "result": {...} },
      "test_execution": { "status": "completed", "worker_id": "worker_5", "result": {...} }
    },
    "final_report": "/storage/reports/LN_LOAN_APPLY_report.md"
  }
}
```

## Error Handling Strategy

Degradation strategy when Workers fail:

| Worker | Failure Impact | Degradation Strategy |
|--------|---------------|---------------------|
| EntryLocator | Critical | Cannot locate entry, AnalysisSession marked FAILED |
| CallTracer | Severe | Continue with limited symbol search results, note incomplete call chain in report |
| BranchAnalyzer | Moderate | Generate basic SQL based on known call chain, may not cover all branches |
| SQLGenerator | Moderate | Continue with template SQL, test data may be less precise |
| TestExecutor | Minor | Record failure reason, continue generating report (includes unexecuted test cases) |

Coordinator decides whether to continue based on criticality:
- P0 Worker (EntryLocator) fails → Fast fail
- P1+ Worker fails → Degrade and continue, note missing information in report

## Best Practices

1. **Worker Context Isolation**
   - Each Worker only receives structured results from previous phases, not raw code
   - Workers use their own context windows to read code and analyze logic

2. **Code Index Dependency**
   - Ensure codebase has been indexed (symbol table, call graph, annotation index)
   - If index missing, Worker will fallback to `read_file` but performance degrades

3. **Branch Coverage Strategy**
   - Prioritize main flow branches (happy path)
   - Second priority: exception branches (parameter validation failure, business rule rejection)
   - Last: boundary conditions (null, empty, extreme values)

4. **Data Safety**
   - Only connect to test environment databases
   - Prefer DELETE + INSERT for SQL operations, avoid UPDATE to prevent data pollution
   - Clean up test data after test completion

## Migration from v1.0

v1.0 Tool → v2.0 Worker mapping:

| v1.0 Tool | v2.0 Worker | Note |
|-----------|-------------|------|
| `analyze_java_project` | EntryLocator + CallTracer | Replaced by index query |
| `list_source_files` | `search_symbol` | Symbol search is more precise |
| `generate_branch_cover_sql` | SQLGenerator Worker | Generated by Agent reasoning |
| `assemble_request_message` | RequestBuilder Worker | Assembled by Agent reasoning |
| `validate_response` | TestExecutor Worker | Validated by Agent direct reasoning |
| `generate_test_report` | ReportGenerator Worker | Generated by Agent aggregation |
| `diagnose_failures` | Built into each Worker | Self-diagnosis on failure |
| `capture_branch_coverage` | TestExecutor statistics | Infer branch trigger from response |

## Troubleshooting

**Issue: EntryLocator cannot find transaction code entry**
- Check if code index has been built: `find_by_annotation` depends on annotation index
- Try fuzzy search: `search_symbol("*LN_LOAN_APPLY*")`
- Verify codebase path is correct

**Issue: CallTracer call chain incomplete**
- Some packages may have been excluded during code indexing, check indexer configuration
- Dynamic calls (reflection) cannot be statically analyzed, requires manual supplement

**Issue: SQLGenerator generated SQL execution fails**
- Use `query_table_structure` to confirm table field names and types
- Check foreign key constraints, ensure dependent data is inserted
- Confirm database user has INSERT/DELETE privileges

**Issue: TestExecutor request sending fails**
- Verify service endpoint is accessible
- Check if `service_id` in request header is correct
- Verify JSON format meets gateway requirements
