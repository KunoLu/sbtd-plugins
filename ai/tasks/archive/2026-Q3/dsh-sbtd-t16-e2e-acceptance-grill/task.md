---
schema_version: 1
id: dsh-sbtd-t16-e2e-acceptance-grill
workflow_mode: null
mode_source: migration-unknown
mode_note: legacy Trellis task without mode proof
status: done
branch: docs/t16-acceptance-record
created_at: null
updated_at: null
completed_at: null
---
# dsh-sbtd-t16-e2e-acceptance-grill

历史任务投影候选。未证明的模式与时间保持未知；完整历史原件保留在私有迁移批次中。

```sbtd-legacy-time-provenance
{
  "created_at": {
    "source": "legacy task.json: createdAt (sidecar or private original)",
    "status": "unproven"
  },
  "updated_at": {
    "source": "legacy task.json: no recorded update time",
    "status": "unproven"
  },
  "completed_at": {
    "source": "legacy task.json: completedAt (sidecar or private original)",
    "status": "unproven"
  }
}
```

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| unknown | unknown | done | legacy completion fact | legacy task.json status |
